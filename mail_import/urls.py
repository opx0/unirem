from django.urls import path

from . import views

app_name = "mail_import"
urlpatterns = [
    path("", views.import_mail, name="import"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/source/", views.source, name="source"),
]
