"""Resource-limited PDF extraction worker, invoked by intake.services."""

import io
import json
import resource
import sys


def main():
    max_file_size = 10 * 1024 * 1024
    max_text_length = 1000000
    output_limit = 6 * max_text_length + 1024
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, output_limit))

    from pypdf import PdfReader

    data = sys.stdin.buffer.read(max_file_size + 1)
    if len(data) > max_file_size:
        result = ("", "The document exceeds the 10 MB extraction limit.")
    else:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            result = ("", "Encrypted PDFs cannot be extracted. Enter text manually.")
        elif len(reader.pages) > 100:
            result = ("", "The PDF exceeds the 100-page extraction limit.")
        else:
            pages = []
            length = 0
            for page in reader.pages:
                text = page.extract_text() or ""
                length += len(text) + 1
                if length > max_text_length:
                    result = ("", "The extracted text exceeds the extraction limit.")
                    break
                pages.append(text)
            else:
                text = "\n".join(pages).strip()
                result = (
                    (text, "")
                    if text
                    else ("", "No readable text was found. Enter text manually.")
                )
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
