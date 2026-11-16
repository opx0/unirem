import hashlib
import io
import json
import logging
import re
import resource
import subprocess
import sys
import tempfile
import warnings
from datetime import date as calendar_date
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils.module_loading import import_string
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PAGES = 100
MAX_TEXT_LENGTH = 1000000
MAX_IMAGE_PIXELS = 20_000_000
OCR_TIMEOUT = 30
PDF_TIMEOUT = 30


# Require an explicit date and time for events; leave ambiguous dates as written.
_DATE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.]\d{1,2}(?:[/.]\d{2,4})?|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?(?:\s+\d{4})?)\b"
    r"(?!\d|[/.\-]\d)",
    re.IGNORECASE,
)
_TIME = re.compile(
    r"\b(?:\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?|"
    r"\d{1,2}\s*(?:a\.?m\.?|p\.?m\.?))\b",
    re.IGNORECASE,
)
_TASK = re.compile(
    r"^(?:please\s+)?(?:submit|complete|return|register|rsvp|respond|bring|"
    r"provide|send|pay|sign|apply)\b",
    re.IGNORECASE,
)
_NOT_ACTIONABLE = re.compile(
    r"\b(?:do\s+not|don't|never|not(?!\s+later\s+than\b)|no\s+need\s+to|has\s+passed|"
    r"have\s+passed|is\s+past|already\s+passed|cancelled|canceled|"
    r"cancellation|postponed|rescheduled|nothing|generated|if|unless|when|whether|in\s+case|"
    r"provided\s+that|subject\s+to|depending\s+on|should\s+you|"
    r"may\s+not|mustn't|cannot|can't|without|no\s+longer|"
    r"occurred|took\s+place|was\s+held)\b",
    re.IGNORECASE,
)
_EVENT = re.compile(
    r"\b(?:meeting|meet|conference|workshop|seminar|webinar|appointment|"
    r"orientation|hearing|ceremony|event|session|lecture|class|"
    r"scheduled|takes\s+place|will\s+be\s+held)\b",
    re.IGNORECASE,
)
_ACTION = re.compile(
    r"\b(?:submit|complete|return|register|rsvp|respond|bring|provide|"
    r"send|pay|sign|apply)\b",
    re.IGNORECASE,
)
_DEADLINE = re.compile(r"^deadline\s*:\s*", re.IGNORECASE)


def _valid_date(value):
    """Validate supported written dates without choosing an ambiguous ordering."""
    value = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", value, flags=re.IGNORECASE)
    if re.search(r"[a-z]", value, re.IGNORECASE):
        value = re.sub(r"\bSept\b", "Sep", value, flags=re.IGNORECASE).replace(".", "")
    try:
        if "-" in value:
            year, month, day = (int(part) for part in value.split("-"))
            calendar_date(year, month, day)
            return True
        if re.fullmatch(r"\d{1,2}[/.]\d{1,2}(?:[/.]\d{2,4})?", value):
            parts = re.split(r"[/.]", value)
            if len(parts) == 3 and len(parts[2]) not in (2, 4):
                return False
            year = int(parts[2]) if len(parts) == 3 else 2000
            if len(parts) == 3 and len(parts[2]) == 2:
                year += 2000
            for month, day in (
                (int(parts[0]), int(parts[1])),
                (int(parts[1]), int(parts[0])),
            ):
                try:
                    calendar_date(year, month, day)
                    return True
                except ValueError:
                    pass
            return False
        value = value.replace(",", "")
        has_year = bool(re.search(r"\b\d{4}$", value))
        if not has_year:
            value += " 2000"
        for pattern in ("%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
            try:
                datetime.strptime(value, pattern)
                return True
            except ValueError:
                pass
    except ValueError:
        return False
    return False


def _valid_time(value):
    value = re.sub(r"[.\s]", "", value).lower()
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", value)
    if not match:
        return False
    hour, minute = int(match[1]), int(match[2] or 0)
    return minute < 60 and (1 <= hour <= 12 if match[3] else 0 <= hour <= 23)


def local_suggestions(text):
    """Find explicit line-level candidates without interpreting dates or time zones."""
    items = []
    for line in text.splitlines():
        evidence = line.strip()
        if not evidence or len(evidence) > 5000 or ";" in evidence:
            continue
        dates = list(_DATE.finditer(evidence))
        times = list(_TIME.finditer(evidence))
        if len(dates) > 1 or len(times) > 1:
            continue
        date = dates[0] if dates else None
        time = times[0] if times else None
        date = date if date and _valid_date(date.group()) else None
        timed = date and time and _valid_time(time.group())
        title = re.sub(r"^\s*(?:[-•*]\s*|\d+[.)]\s+)", "", evidence).strip()
        if _NOT_ACTIONABLE.search(title):
            continue
        deadline_label = _DEADLINE.match(title)
        deadline = deadline_label and timed
        if deadline:
            title_date = _DATE.search(title)
            title_time = _TIME.search(title)
            if (
                title[deadline_label.end() : title_date.start()].strip()
                or title_date.end() > title_time.start()
                or title[title_date.end() : title_time.start()].strip().lower()
                not in ("", "at", ",", ", at")
                or title[title_time.end() :].strip(" .")
            ):
                continue
        task = _TASK.match(title) or deadline
        if task and not deadline and len(_ACTION.findall(title)) != 1:
            continue
        if deadline and _ACTION.search(title):
            continue
        if not task and not _EVENT.search(title):
            continue
        if not timed and not task:
            continue
        kind = "task" if task else "event"
        if kind == "event" and date.start() > 0:
            title = evidence[: date.start()].strip(" \t-–—,:;") or title
        date_text = ""
        if date:
            start, end = date.span()
            if timed:
                start, end = min(start, time.start()), max(end, time.end())
            if end - start > 200:
                continue
            date_text = evidence[start:end]
        items.append(
            {
                "kind": kind,
                "title": title[:200],
                "description": "",
                "date_text": date_text,
                "evidence": evidence,
            }
        )
        if len(items) == 50:
            break
    return items


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
            data = source.read(MAX_FILE_SIZE + 1)
            if len(data) > MAX_FILE_SIZE:
                return "", "The document exceeds the 10 MB extraction limit."
            if not data.startswith(b"%PDF-"):
                return "", "The document is not a readable PDF."
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("pdf_extract.py"))],
                input=data,
                stdout=output,
                stderr=subprocess.DEVNULL,
                timeout=PDF_TIMEOUT,
                check=False,
            )
            if result.returncode:
                return (
                    "",
                    "The document could not be read. Retry or enter text manually.",
                )
            output.seek(0)
            payload = output.read(6 * MAX_TEXT_LENGTH + 1025)
            if len(payload) > 6 * MAX_TEXT_LENGTH + 1024:
                return "", "The extracted text exceeds the extraction limit."
            text, error = json.loads(payload)
            if not isinstance(text, str) or not isinstance(error, str):
                raise TypeError("Invalid PDF extraction response")
            if len(text) > MAX_TEXT_LENGTH:
                return "", "The extracted text exceeds the extraction limit."
            return text, error
    except subprocess.TimeoutExpired:
        return "", "PDF extraction timed out. Retry or enter text manually."
    except Exception:
        logger.exception("Document extraction failed for document %s", document.pk)
        return "", "The document could not be read. Retry or enter text manually."
