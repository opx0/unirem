from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Task

from .models import ChecklistItem


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ("title",)


@login_required
def detail(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk, owner=request.user)
    return render(
        request,
        "checklist/detail.html",
        {
            "task": task,
            "items": task.checklist_items.all(),
            "form": ChecklistItemForm(),
        },
    )


@login_required
@require_POST
def add(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk, owner=request.user)
    form = ChecklistItemForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.task = task
        item.save()
        return redirect("checklist:detail", task_pk=task.pk)
    return render(
        request,
        "checklist/detail.html",
        {"task": task, "items": task.checklist_items.all(), "form": form},
    )


@login_required
@require_POST
def toggle(request, task_pk, item_pk):
    item = get_object_or_404(
        ChecklistItem, pk=item_pk, task_id=task_pk, task__owner=request.user
    )
    ChecklistItem.objects.filter(pk=item.pk).update(completed=~F("completed"))
    return redirect("checklist:detail", task_pk=task_pk)


@login_required
@require_POST
def delete(request, task_pk, item_pk):
    item = get_object_or_404(
        ChecklistItem, pk=item_pk, task_id=task_pk, task__owner=request.user
    )
    item.delete()
    return redirect("checklist:detail", task_pk=task_pk)
