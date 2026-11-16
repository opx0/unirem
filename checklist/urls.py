from django.urls import path

from . import views

app_name = "checklist"

urlpatterns = [
    path("<int:task_pk>/", views.detail, name="detail"),
    path("<int:task_pk>/add/", views.add, name="add"),
    path("<int:task_pk>/items/<int:item_pk>/toggle/", views.toggle, name="toggle"),
    path("<int:task_pk>/items/<int:item_pk>/delete/", views.delete, name="delete"),
]
