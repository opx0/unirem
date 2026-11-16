from django.urls import path

from . import views

app_name = "connections"

urlpatterns = [
    path("", views.settings, name="settings"),
    path("manual/connect/", views.connect_manual, name="connect_manual"),
    path("manual/disconnect/", views.disconnect_manual, name="disconnect_manual"),
]
