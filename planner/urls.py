from django.urls import path

from . import views

app_name = "planner"

urlpatterns = [
    path("", views.agenda, name="agenda"),
    path("tasks/", views.tasks, name="tasks"),
    path("<str:kind>/new/", views.record_form, name="new"),
    path("<str:kind>/<int:pk>/edit/", views.record_form, name="edit"),
    path("tasks/<int:pk>/toggle/", views.toggle_task, name="toggle_task"),
    path("events/<int:pk>/complete/", views.complete_event, name="complete_event"),
]
