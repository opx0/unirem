from datetime import UTC, date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import Event


def _escape_text(value):
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(
        char for char in value if char == "\n" or ord(char) >= 32 and ord(char) != 127
    )
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold_line(line):
    # The 75-octet limit includes the leading space on continuation lines.
    parts = []
    current = ""
    size = 0
    for char in line:
        char_size = len(char.encode("utf-8"))
        if size + char_size > 75:
            parts.append(current)
            current = " "
            size = 1
        current += char
        size += char_size
    parts.append(current)
    return "\r\n".join(parts)


def _utc(value):
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_default_timezone())
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


@login_required
@require_GET
def download(request):
    stamp = _utc(timezone.now())
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Campus Radar//Calendar Export//EN",
        "CALSCALE:GREGORIAN",
    ]
    for event in Event.objects.filter(owner=request.user).order_by("pk").iterator():
        if not event.date_only and not event.starts_at:
            continue
        lines.extend(
            ["BEGIN:VEVENT", f"UID:event-{event.pk}@campus-radar", f"DTSTAMP:{stamp}"]
        )
        if event.date_only:
            lines.append(f"DTSTART;VALUE=DATE:{event.date_only:%Y%m%d}")
            if event.date_only < date.max:
                end = event.date_only + timedelta(days=1)
                lines.append(f"DTEND;VALUE=DATE:{end:%Y%m%d}")
        else:
            lines.append(f"DTSTART:{_utc(event.starts_at)}")
            if event.ends_at and event.ends_at > event.starts_at:
                lines.append(f"DTEND:{_utc(event.ends_at)}")
        lines.append(f"SUMMARY:{_escape_text(event.title)}")
        if event.location:
            lines.append(f"LOCATION:{_escape_text(event.location)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    content = "\r\n".join(_fold_line(line) for line in lines) + "\r\n"
    response = HttpResponse(content, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="campus-radar.ics"'
    response["Cache-Control"] = "private, no-store"
    return response
