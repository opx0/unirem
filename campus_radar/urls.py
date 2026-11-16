from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import health, pwa
from discovery import views as discovery_views
from login_security.views import ThrottledLoginView

urlpatterns = [
    path("manifest.webmanifest", pwa.manifest, name="pwa_manifest"),
    path("service-worker.js", pwa.service_worker, name="pwa_service_worker"),
    path("health/live/", health.live, name="health_live"),
    path("health/ready/", health.ready, name="health_ready"),
    path("admin/", admin.site.urls),
    path("accounts/login/", ThrottledLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("intake/", include("intake.urls")),
    path("reminders/", include("reminders.urls")),
    path("planner/", include("planner.urls")),
    path("calendar-export/", include("calendar_export.urls")),
    path("revisions/", include("revisions.urls")),
    path("connections/", include("connections.urls")),
    path("checklist/", include("checklist.urls")),
    path("search/", discovery_views.search, name="search"),
    path("quiet-hours/", include("quiet_hours.urls")),
    path("answers/", include("answers.urls")),
    path("mail-import/", include("mail_import.urls")),
    path("", include("core.urls")),
]
