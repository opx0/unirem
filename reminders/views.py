from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Event, Task

from .forms import ReminderForm
from .models import NotificationDelivery, Reminder


@login_required
def reminder_list(request):
    items = Reminder.objects.filter(owner=request.user).select_related(
        "event", "task", "delivery"
    )
    notifications = (
        NotificationDelivery.objects.filter(
            reminder__owner=request.user, dismissed_at__isnull=True
        )
        .select_related("reminder__event", "reminder__task")
        .order_by("-delivered_at", "-pk")
    )
    return render(
        request, "reminders/list.html", {"items": items, "notifications": notifications}
    )


@login_required
def reminder_create(request):
    form = ReminderForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                selected = form.cleaned_data["event"] or form.cleaned_data["task"]
                model = Event if form.cleaned_data["event"] else Task
                target = model.objects.select_for_update().get(
                    pk=selected.pk, owner=request.user
                )
                changed = target.completed
                if isinstance(target, Event):
                    changed |= (
                        target.starts_at != selected.starts_at
                        or target.date_only != selected.date_only
                    )
                else:
                    changed |= target.due_date != selected.due_date
                if changed:
                    form.add_error(
                        None,
                        "The target changed. Please review the reminder and try again.",
                    )
                else:
                    values = {
                        "owner": request.user,
                        "relative_minutes": form.cleaned_data["minutes_before"],
                        "event_starts_at": target.starts_at
                        if isinstance(target, Event)
                        else None,
                        "event_date_only": target.date_only
                        if isinstance(target, Event)
                        else None,
                        "task_due_date": target.due_date
                        if isinstance(target, Task)
                        else None,
                        "state": Reminder.State.PENDING,
                        "cancellation_reason": "",
                        "attempts": 0,
                        "next_attempt_at": None,
                    }
                    lookup = {
                        "event": target if isinstance(target, Event) else None,
                        "task": target if isinstance(target, Task) else None,
                        "scheduled_at": form.cleaned_data["scheduled_at"],
                    }
                    cancelled = (
                        Reminder.objects.select_for_update()
                        .filter(
                            **lookup, owner=request.user, state=Reminder.State.CANCELLED
                        )
                        .order_by("pk")
                        .first()
                    )
                    if cancelled:
                        Reminder.objects.filter(
                            pk=cancelled.pk, state=Reminder.State.CANCELLED
                        ).update(**values)
                    else:
                        Reminder.objects.create(**lookup, **values)
                    messages.success(request, "Reminder scheduled.")
                    return redirect("reminders:list")
        except IntegrityError:
            form.add_error(None, "A reminder already exists for this target and time.")
        except (Event.DoesNotExist, Task.DoesNotExist):
            form.add_error(None, "The target is no longer available.")
    return render(
        request,
        "core/form.html",
        {"form": form, "heading": "New reminder", "submit": "Schedule reminder"},
    )


@login_required
@require_POST
def reminder_cancel(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, owner=request.user)
    Reminder.objects.filter(pk=reminder.pk, state=Reminder.State.PENDING).update(
        state=Reminder.State.CANCELLED, cancellation_reason="Cancelled by you."
    )
    return redirect("reminders:list")


@login_required
@require_POST
def notification_clear(request):
    NotificationDelivery.objects.filter(
        reminder__owner=request.user, dismissed_at__isnull=True
    ).update(dismissed_at=timezone.now())
    return redirect("reminders:list")
