from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from .models import QuietHoursPreference


def _boundary(day, wall_time, zone, *, end):
    """Resolve folds conservatively and move nonexistent wall times forward."""
    naive = datetime.combine(day, wall_time)
    candidates = []
    for fold in (0, 1):
        instant = naive.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        local = instant.astimezone(zone).replace(tzinfo=None)
        candidates.append((instant, local))
    valid = [instant for instant, local in candidates if local == naive]
    if valid:
        return max(valid) if end else min(valid)
    # A spring-forward gap maps one candidate backward and the other forward.
    return min(instant for instant, local in candidates if local > naive)


def defer_until(user, instant):
    """Return the quiet interval's end in UTC, or None if delivery is allowed.

    The supplied instant must be timezone-aware. Missing or disabled preferences
    never defer; a missing profile uses the project's default timezone.
    """
    if timezone.is_naive(instant):
        raise ValueError("instant must be timezone-aware")
    preference = QuietHoursPreference.objects.filter(owner=user, enabled=True).first()
    if preference is None:
        return None
    profile = getattr(user, "studentprofile", None)
    zone = ZoneInfo(profile.timezone if profile else settings.TIME_ZONE)
    now = instant.astimezone(UTC)
    today = now.astimezone(zone).date()
    for day in (today - timedelta(days=1), today):
        end_day = day + timedelta(days=preference.end_time <= preference.start_time)
        start = _boundary(day, preference.start_time, zone, end=False)
        end = _boundary(end_day, preference.end_time, zone, end=True)
        if start <= now < end:
            return end
    return None
