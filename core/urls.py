from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("settings/", views.profile, name="profile"),
    path("settings/privacy/", views.privacy, name="privacy"),
    path("settings/export/", views.export_data, name="export_data"),
    path("settings/delete/", views.delete_account, name="delete_account"),
    path("inbox/", views.inbox, name="inbox"),
    path("capture/", views.capture, name="capture"),
    path("inbox/<int:pk>/", views.notice_detail, name="notice"),
    path("inbox/<int:pk>/edit/", views.notice_edit, name="notice_edit"),
    path(
        "source/<int:pk>/download/", views.document_download, name="document_download"
    ),
    path("source/<int:pk>/preview/", views.document_preview, name="document_preview"),
    path("events/", views.records, {"kind": "events"}, name="events"),
    path("tasks/", views.records, {"kind": "tasks"}, name="tasks"),
    path(
        "opportunities/", views.records, {"kind": "opportunities"}, name="opportunities"
    ),
    path("<str:kind>/", views.records, name="records"),
    path("<str:kind>/new/", views.record_form, name="record_new"),
    path("<str:kind>/<int:pk>/edit/", views.record_form, name="record_edit"),
    path("tasks/<int:pk>/toggle/", views.toggle_task, name="toggle_task"),
]
