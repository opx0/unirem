from zoneinfo import ZoneInfo

from django.utils import timezone


class ProfileTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = getattr(request.user, "studentprofile", None)
            if profile:
                timezone.activate(ZoneInfo(profile.timezone))
            else:
                timezone.deactivate()
        else:
            timezone.deactivate()
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
