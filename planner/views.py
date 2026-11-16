from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, DateField, F, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce, TruncDate
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import EventForm, TaskForm
from core.models import Event, Task


@login_required
def agenda(request):
    now = timezone.now()
    kind = request.GET.get("kind", "")
    events = Event.objects.filter(owner=request.user, completed=False)
    current = events.filter(
        Q(date_only__gte=timezone.localdate())
        | Q(starts_at__gte=now)
        | Q(starts_at__lt=now, ends_at__gt=now)
    )
    if kind in Event.Kind.values:
        current = current.filter(kind=kind)
    else:
        kind = ""
    current = list(
        current.select_related("notice", "opportunity")
        .annotate(
            day=Coalesce("date_only", TruncDate("starts_at"), output_field=DateField())
        )
        .order_by("day", "starts_at", "pk")
    )
    # Only explicit intervals can establish an overlap; adjacent endpoints do not.
    intervals = list(events.filter(starts_at__isnull=False, ends_at__isnull=False))
    for event in current:
        event.conflicts = [
            other
            for other in intervals
            if event.ends_at
            and event.starts_at
            and other.pk != event.pk
            and event.starts_at < other.ends_at
            and other.starts_at < event.ends_at
        ]
    return render(
        request,
        "planner/agenda.html",
        {
            "events": current,
            "kind": kind,
            "kinds": Event.Kind.choices,
        },
    )


@login_required
def tasks(request):
    status = request.GET.get("status", "open")
    priority = request.GET.get("priority", "")
    items = Task.objects.filter(owner=request.user).select_related(
        "notice", "opportunity"
    )
    if status == "open":
        items = items.filter(completed=False)
    elif status == "completed":
        items = items.filter(completed=True)
    else:
        status = "all"
    priorities = Task._meta.get_field("priority").choices
    if priority in dict(priorities):
        items = items.filter(priority=priority)
    else:
        priority = ""
    items = items.annotate(
        priority_order=Case(
            When(priority="high", then=Value(0)),
            When(priority="normal", then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by("completed", "priority_order", F("due_date").asc(nulls_last=True), "pk")
    return render(
        request,
        "planner/tasks.html",
        {
            "tasks": items,
            "status": status,
            "priority": priority,
            "priorities": priorities,
        },
    )


@login_required
def record_form(request, kind, pk=None):
    mapping = {
        "events": (Event, EventForm, "planner:agenda"),
        "tasks": (Task, TaskForm, "planner:tasks"),
    }
    if kind not in mapping:
        raise Http404
    model, form_type, destination = mapping[kind]
    instance = get_object_or_404(model, owner=request.user, pk=pk) if pk else None
    form = form_type(request.POST or None, instance=instance, owner=request.user)
    form.instance.owner = request.user
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{model.__name__} saved.")
        return redirect(destination)
    return render(
        request,
        "planner/form.html",
        {
            "form": form,
            "heading": f"{'Edit' if pk else 'New'} {model.__name__.lower()}",
            "destination": destination,
        },
    )


@login_required
@require_POST
def toggle_task(request, pk):
    task = get_object_or_404(Task, owner=request.user, pk=pk)
    task.completed = not task.completed
    task.save(update_fields=["completed"])
    return redirect("planner:tasks")
