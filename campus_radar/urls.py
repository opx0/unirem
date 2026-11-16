from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import health
from discovery import views as discovery_views

urlpatterns = [
    path("health/live/", health.live, name="health_live"),
    path("health/ready/", health.ready, name="health_ready"),
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
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
    path("", include("core.urls")),
]
