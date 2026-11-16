from django.urls import path

from . import views

app_name = "calendar_export"

urlpatterns = [
    path("", views.options, name="options"),
    path("download/", views.download, name="download"),
]
