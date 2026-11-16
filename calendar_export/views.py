from datetime import UTC, date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.template import engines
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_GET

from core.models import Event, Task
from reminders.models import Reminder


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


def _uid(owner_id, kind, pk):
    return (
        salted_hmac("campus-radar-calendar", f"{owner_id}:{kind}:{pk}").hexdigest()
        + "@campus-radar"
    )


def _alarm_lines(reminder, title):
    return [
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"TRIGGER;VALUE=DATE-TIME:{_utc(reminder.scheduled_at)}",
        f"DESCRIPTION:{_escape_text(title)}",
        "END:VALARM",
    ]


@login_required
@require_GET
def options(request):
    template = engines["django"].from_string(
        """{% extends 'core/base.html' %}{% block title %}Export calendar{% endblock %}
        {% block content %}<h1>Export calendar</h1>
        <p>Download your events and tasks as an iCalendar (.ics) file to import into a calendar or task app.</p>
        <p><a href="{% url 'calendar_export:download' %}">Download without alarms</a></p>
        <p><a href="{% url 'calendar_export:download' %}?alarms=1">Download with pending reminder alarms</a></p>
        <p><a href="{% url 'calendar_export:download' %}?week=1">Download the next week with reminders</a></p>
        <p>For offline use, download the next-week file while online and import it into a calendar app on your device. Enable notifications for that app and device, and check that the imported alarms are present. Apps may not support task or alarm imports, and neither the app nor this PWA can guarantee offline alerts.</p>
        <p>The next-week snapshot includes timed events starting in the next 168 hours and all-day events dated today through six days from today, using your local dates. It also includes events and tasks with pending reminders in the next 168 hours, and all pending reminders for those records. Records without an event date or time cannot be exported as events.</p>
        <p>An assessment duration is an allowance, not an event end time. When no end time is saved, the export leaves it unknown.</p>
        <p>The alarm export includes pending reminders for timed events, explicitly scheduled reminders for all-day events, and task reminders. Import support for tasks and alarms is not guaranteed: apps may ignore them or handle them differently. Offline alerts depend on the app and device after import; this website does not deliver offline alerts.</p>
        <p>Importing is a snapshot: later reminder changes in Campus Radar will not update your calendar. Calendar identifiers may have changed since earlier exports, so importing again may create duplicates.</p>
        {% endblock %}"""
    )
    return HttpResponse(template.render({}, request))


@login_required
@require_GET
def download(request):
    now = timezone.now()
    stamp = _utc(now)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Campus Radar//Calendar Export//EN",
        "CALSCALE:GREGORIAN",
    ]
    events = Event.objects.filter(owner=request.user).order_by("pk")
    one_week = request.GET.get("week") == "1"
    include_alarms = one_week or request.GET.get("alarms") == "1"
    if one_week:
        end = now + timedelta(days=7)
        today = timezone.localdate(now)
        end_date = today + timedelta(days=6)
        upcoming_reminders = Reminder.objects.filter(
            owner=request.user,
            state=Reminder.State.PENDING,
            scheduled_at__gte=now,
            scheduled_at__lt=end,
        )
        events = events.filter(
            Q(date_only__isnull=True, starts_at__gte=now, starts_at__lt=end)
            | Q(date_only__gte=today, date_only__lte=end_date)
            | Q(pk__in=upcoming_reminders.filter(task__isnull=True).values("event_id"))
        )
    if include_alarms:
        events = events.prefetch_related(
            Prefetch(
                "reminders",
                queryset=Reminder.objects.filter(
                    owner=request.user, state=Reminder.State.PENDING, task__isnull=True
                ).order_by("scheduled_at", "pk"),
                to_attr="export_reminders",
            )
        )
    for event in events.iterator(chunk_size=200):
        if not event.date_only and not event.starts_at:
            continue
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{_uid(request.user.pk, 'event', event.pk)}",
                f"DTSTAMP:{stamp}",
            ]
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
        if include_alarms:
            for reminder in event.export_reminders:
                if not event.date_only or reminder.relative_minutes is None:
                    lines.extend(_alarm_lines(reminder, event.title))
        lines.append("END:VEVENT")
    tasks = Task.objects.filter(owner=request.user).order_by("pk")
    if one_week:
        tasks = tasks.filter(
            pk__in=upcoming_reminders.filter(event__isnull=True).values("task_id")
        )
    if include_alarms:
        tasks = tasks.prefetch_related(
            Prefetch(
                "reminders",
                queryset=Reminder.objects.filter(
                    owner=request.user,
                    state=Reminder.State.PENDING,
                    event__isnull=True,
                    relative_minutes__isnull=True,
                ).order_by("scheduled_at", "pk"),
                to_attr="export_reminders",
            )
        )
    for task in tasks.iterator(chunk_size=200):
        lines.extend(
            [
                "BEGIN:VTODO",
                f"UID:{_uid(request.user.pk, 'task', task.pk)}",
                f"DTSTAMP:{stamp}",
            ]
        )
        lines.append(f"SUMMARY:{_escape_text(task.title)}")
        if task.description:
            lines.append(f"DESCRIPTION:{_escape_text(task.description)}")
        if task.due_date:
            lines.append(f"DUE;VALUE=DATE:{task.due_date:%Y%m%d}")
        if task.completed:
            lines.append("STATUS:COMPLETED")
        if include_alarms:
            for reminder in task.export_reminders:
                lines.extend(_alarm_lines(reminder, task.title))
        lines.append("END:VTODO")
    lines.append("END:VCALENDAR")
    content = "\r\n".join(_fold_line(line) for line in lines) + "\r\n"
    response = HttpResponse(content, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="campus-radar.ics"'
    response["Cache-Control"] = "private, no-store"
    return response
