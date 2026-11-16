import hashlib
import io
import logging
import resource
import subprocess
import tempfile
import warnings
from pathlib import Path

from django.conf import settings
from django.utils.module_loading import import_string
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

logger = logging.getLogger(__name__)
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PAGES = 100
MAX_TEXT_LENGTH = 1000000
MAX_IMAGE_PIXELS = 20_000_000
OCR_TIMEOUT = 30


def _ocr_limits():
    # Limit the child only; never change the web worker's resource limits.
    resource.setrlimit(resource.RLIMIT_CPU, (OCR_TIMEOUT, OCR_TIMEOUT))
    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
    resource.setrlimit(
        resource.RLIMIT_FSIZE, (4 * MAX_TEXT_LENGTH, 4 * MAX_TEXT_LENGTH)
    )


def _extract_image(document):
    if getattr(settings, "INTAKE_OCR_ENABLED", False) is not True:
        return "", "Image OCR is not enabled. Enter text manually."

    formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
    expected = formats.get(Path(document.original_name).suffix.lower())
    if not expected:
        return "", "The image format is not supported. Enter text manually."
    try:
        with document.file.open("rb") as source:
            data = source.read(MAX_FILE_SIZE + 1)
        if len(data) > MAX_FILE_SIZE:
            return "", "The document exceeds the 10 MB extraction limit."
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != expected or getattr(image, "n_frames", 1) != 1:
                    return "", "The image is not a supported single-frame image."
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    return "", "The image exceeds the OCR pixel limit."
                image.verify()

        # stdin/stdout avoid exposing document paths or using a shell or network service.
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(
                ["tesseract", "stdin", "stdout"],
                input=data,
                stdout=output,
                stderr=subprocess.DEVNULL,
                timeout=OCR_TIMEOUT,
                preexec_fn=_ocr_limits,
                check=False,
            )
            if result.returncode:
                return "", "Image OCR failed. Retry or enter text manually."
            output.seek(0)
            text = output.read(4 * MAX_TEXT_LENGTH + 1).decode("utf-8").strip()
        if len(text) > MAX_TEXT_LENGTH:
            return "", "The extracted text exceeds the extraction limit."
        if not text:
            return "", "No readable text was found. Enter text manually."
        return text, ""
    except FileNotFoundError:
        return "", "Image OCR is unavailable. Enter text manually."
    except subprocess.TimeoutExpired:
        return "", "Image OCR timed out. Retry or enter text manually."
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return "", "The image could not be read or exceeds the OCR pixel limit."
    except Exception:
        logger.exception("Image extraction failed for document %s", document.pk)
        return "", "The image could not be read. Retry or enter text manually."


def ai_suggestions(text):
    """Call the configured provider and validate its entire response before saving."""
    provider_path = getattr(settings, "INTAKE_AI_PROVIDER", "")
    if not provider_path:
        raise ValueError(
            "AI extraction is not configured. Continue with manual review."
        )
    try:
        result = import_string(provider_path)(text)
        if not isinstance(result, list) or len(result) > 50:
            raise ValueError("Invalid response")
        for item in result:
            if not isinstance(item, dict) or set(item) != {
                "kind",
                "title",
                "description",
                "date_text",
                "evidence",
            }:
                raise ValueError("Invalid fields")
            if item["kind"] not in ("event", "task", "information"):
                raise ValueError("Invalid kind")
            for key, maximum in (
                ("title", 200),
                ("description", 5000),
                ("date_text", 200),
                ("evidence", 5000),
            ):
                if not isinstance(item[key], str) or len(item[key]) > maximum:
                    raise ValueError("Invalid field value")
            if (
                not item["title"].strip()
                or not item["evidence"].strip()
                or item["evidence"] not in text
            ):
                raise ValueError("Missing source evidence")
        return result
    except Exception as exc:
        logger.warning("AI extraction failed: %s", type(exc).__name__)
        raise ValueError(
            "AI extraction failed or returned invalid evidence. Continue with manual review."
        ) from exc


def text_hash(text):
    normalized = " ".join(text.split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def extract_document(document):
    if not document:
        return "", "No document is attached. Enter text manually."
    if Path(document.original_name).suffix.lower() != ".pdf":
        return _extract_image(document)
    try:
        with document.file.open("rb") as source:
            source.seek(0, 2)
            if source.tell() > MAX_FILE_SIZE:
                return "", "The document exceeds the 10 MB extraction limit."
            source.seek(0)
            if source.read(5) != b"%PDF-":
                return "", "The document is not a readable PDF."
            source.seek(0)
            reader = PdfReader(source)
            if reader.is_encrypted:
                return "", "Encrypted PDFs cannot be extracted. Enter text manually."
            if len(reader.pages) > MAX_PAGES:
                return "", "The PDF exceeds the 100-page extraction limit."
            pages = []
            length = 0
            for page in reader.pages:
                text = page.extract_text() or ""
                length += len(text) + 1
                if length > MAX_TEXT_LENGTH:
                    return "", "The extracted text exceeds the extraction limit."
                pages.append(text)
            text = "\n".join(pages).strip()
            if not text:
                return "", "No readable text was found. Enter text manually."
            return text, ""
    except Exception:
        logger.exception("Document extraction failed for document %s", document.pk)
        return "", "The document could not be read. Retry or enter text manually."
