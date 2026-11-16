from django.urls import path

from . import views

app_name = "calendar_export"

urlpatterns = [
    path("download/", views.download, name="download"),
]
