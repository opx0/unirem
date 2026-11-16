from django.urls import path

from . import views

app_name = "intake"

urlpatterns = [
    path("<int:pk>/", views.review, name="review"),
    path("<int:pk>/extract/", views.extract, name="extract"),
    path("<int:pk>/manual/", views.manual, name="manual"),
    path("<int:pk>/runs/<int:run_pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/runs/<int:run_pk>/suggest/", views.suggest, name="suggest"),
    path(
        "<int:pk>/suggestions/<int:suggestion_pk>/",
        views.review_suggestion,
        name="suggestion",
    ),
    path(
        "<int:pk>/suggestions/<int:suggestion_pk>/convert/",
        views.convert_suggestion,
        name="convert_suggestion",
    ),
]
