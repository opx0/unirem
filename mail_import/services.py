from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_TEXT_LENGTH = 1000000
MAX_PARTS = 200
MAX_DEPTH = 20


class MailError(ValueError):
    pass


class TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template", "head"):
            self.hidden += 1
        elif not self.hidden and tag in ("p", "div", "br", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template", "head") and self.hidden:
            self.hidden -= 1
        elif not self.hidden and tag in ("p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse_mail(raw):
    if not raw or len(raw) > MAX_FILE_SIZE or b"\x00" in raw:
        raise MailError("The email is empty, invalid, or exceeds 5 MB.")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        if not message.keys() or not any(
            message.get(h) for h in ("From", "Subject", "Date")
        ):
            raise MailError("The file does not contain email headers.")
        if message.defects:
            raise MailError("The email headers or MIME structure are invalid.")
        stack = [(message, 0, False)]
        results = {}
        count = 0
        while stack:
            part, depth, visited = stack.pop()
            if visited:
                children = [results[id(p)] for p in part.get_payload()]
                if part.get_content_subtype() == "alternative":
                    # Alternatives represent the same content, unlike mixed parts.
                    selected = next((c for c in children if c[1]), None)
                    if selected is None:
                        selected = next((c for c in children if c[0]), ([], False))
                    results[id(part)] = selected
                else:
                    results[id(part)] = (
                        [text for texts, _ in children for text in texts],
                        any(has_plain for _, has_plain in children),
                    )
                continue
            count += 1
            if count > MAX_PARTS or depth > MAX_DEPTH or part.defects:
                raise MailError("The email MIME structure is invalid or too complex.")
            if part.get_content_disposition() == "attachment" or part.get_filename():
                results[id(part)] = ([], False)
                continue
            if part.get_content_maintype() == "multipart":
                if not part.is_multipart():
                    raise MailError("The email MIME structure is invalid.")
                stack.append((part, depth, True))
                stack.extend(
                    (p, depth + 1, False) for p in reversed(part.get_payload())
                )
            elif part.get_content_type() in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload is None or part.defects:
                    raise MailError("The email body encoding is invalid.")
                charset = part.get_content_charset() or "utf-8"
                try:
                    text = payload.decode(charset, errors="replace")
                except LookupError:
                    text = payload.decode("utf-8", errors="replace")
                text = text.replace("\x00", "")
                is_plain = part.get_content_type() == "text/plain"
                if not is_plain:
                    parser = TextHTMLParser()
                    parser.feed(text)
                    parser.close()
                    text = "".join(parser.parts)
                results[id(part)] = ([text], is_plain)
            else:
                results[id(part)] = ([], False)
        text = "\n\n".join(results[id(message)][0])
        text = text.strip()
        if not text or len(text) > MAX_TEXT_LENGTH:
            raise MailError("The email has no usable text or its text is too long.")
        sender = str(message.get("From", ""))
        subject = str(message.get("Subject", ""))
        date_header = str(message.get("Date", ""))
        try:
            sent_at = parsedate_to_datetime(date_header)
            if sent_at and sent_at.utcoffset() is None:
                sent_at = None
        except (TypeError, ValueError, OverflowError):
            sent_at = None
        return {
            "sender": sender,
            "subject": subject,
            "date_header": date_header,
            "sent_at": sent_at,
            "text": text,
        }
    except (RecursionError, ValueError, TypeError, IndexError) as exc:
        if isinstance(exc, MailError):
            raise
        raise MailError("The email could not be parsed safely.") from exc
