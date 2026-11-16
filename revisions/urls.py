from django.urls import path

from . import views

app_name = "revisions"

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:first_pk>/<int:second_pk>/", views.compare, name="compare"),
    path(
        "<int:first_pk>/<int:second_pk>/event-change/",
        views.propose_event_change,
        name="propose_event_change",
    ),
    path("event-change/<int:pk>/", views.event_change, name="event_change"),
]
