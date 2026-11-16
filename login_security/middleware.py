from django.contrib.admin import AdminSite
from django.db import DatabaseError
from django.http import HttpResponse

from .views import WINDOW, _consume, _login_keys, _release


class AdminLoginThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if (
            request.method != "POST"
            or not isinstance(getattr(view_func, "__self__", None), AdminSite)
            or getattr(view_func, "__name__", None) != "login"
        ):
            return None

        try:
            reservations = _consume(_login_keys(request))
        except DatabaseError:
            return HttpResponse("Login temporarily unavailable.", status=503)
        if reservations is None:
            response = HttpResponse(
                "Too many login attempts. Try again later.", status=429
            )
            response["Retry-After"] = str(int(WINDOW.total_seconds()))
            return response

        user_before = request.user
        response = view_func(request, *view_args, **view_kwargs)
        # django.contrib.auth.login replaces request.user on successful login.
        if request.user is not user_before and request.user.is_authenticated:
            try:
                _release(reservations)
            except DatabaseError:
                pass
        return response
