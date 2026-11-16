import hashlib
import hmac
import ipaddress
import random
import unicodedata
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.views import LoginView
from django.db import DatabaseError, transaction
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone

from .models import LoginThrottle

WINDOW = timedelta(minutes=15)
ACCOUNT_LIMIT = 5
IP_LIMIT = 50


def _key(kind, value):
    # Store neither usernames nor addresses in the throttle table.
    message = f"{kind}:{value}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _client_ip(request):
    # Forwarded headers are attacker-controlled unless a trusted proxy removes them.
    # REMOTE_ADDR is deliberately used even behind a proxy (all clients then share
    # its limit); deployments may set it to a verified client address upstream.
    try:
        return str(ipaddress.ip_address(request.META.get("REMOTE_ADDR", "")))
    except ValueError:
        return "unknown"


def _login_keys(request):
    ip = _client_ip(request)
    keys = [(_key("ip", ip), IP_LIMIT)]
    username = unicodedata.normalize(
        "NFKC", request.POST.get("username", "").strip()
    ).casefold()
    if username:
        keys.append((_key("account-ip", f"{len(ip)}:{ip}:{username}"), ACCOUNT_LIMIT))
    return keys


def _consume(keys):
    now = timezone.now()
    # Opportunistic expiry keeps storage bounded without an external scheduler.
    if random.randrange(100) == 0:
        LoginThrottle.objects.filter(expires_at__lte=now).delete()

    reservations = []
    with transaction.atomic():
        for key, limit in keys:
            LoginThrottle.objects.select_for_update().get_or_create(
                key=key, defaults={"expires_at": now + WINDOW}
            )
            LoginThrottle.objects.filter(key=key, expires_at__lte=now).update(
                attempts=0, expires_at=now + WINDOW
            )
            # Conditional database updates prevent concurrent requests from
            # admitting more than the configured number per window.
            admitted = LoginThrottle.objects.filter(key=key, attempts__lt=limit).update(
                attempts=F("attempts") + 1
            )
            if not admitted:
                # A rejected request must not spend any other bucket's budget.
                transaction.set_rollback(True)
                return None
            expires_at = LoginThrottle.objects.values_list("expires_at", flat=True).get(
                key=key
            )
            reservations.append((key, expires_at))
    return reservations


def _release(reservations):
    with transaction.atomic():
        for key, expires_at in reservations:
            # Do not subtract a reservation from a later window.
            LoginThrottle.objects.filter(
                key=key, expires_at=expires_at, attempts__gt=0
            ).update(attempts=F("attempts") - 1)


class ThrottledLoginView(LoginView):
    def post(self, request, *args, **kwargs):
        try:
            self.reservations = _consume(_login_keys(request))
        except DatabaseError:
            # Authentication must not silently bypass throttling during an outage.
            return HttpResponse("Login temporarily unavailable.", status=503)
        if self.reservations is None:
            response = HttpResponse(
                "Too many login attempts. Try again later.", status=429
            )
            response["Retry-After"] = str(int(WINDOW.total_seconds()))
            return response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        try:
            _release(self.reservations)
        except DatabaseError:
            # Keep the reservation if it cannot safely be released.
            pass
        return response
