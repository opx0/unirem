from django.urls import path

from . import views

app_name = "quiet_hours"
urlpatterns = [path("", views.settings, name="settings")]
