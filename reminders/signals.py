from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import Event, Task

from .models import Reminder


@receiver(post_save, sender=Event)
def cancel_changed_event_reminders(sender, instance, using, **kwargs):
    with transaction.atomic(using=using):
        event = (
            Event.objects.using(using)
            .select_for_update()
            .filter(pk=instance.pk)
            .first()
        )
        if not event:
            return
        pending = (
            Reminder.objects.using(using)
            .select_for_update()
            .filter(event=event, state=Reminder.State.PENDING)
        )
        changed = [
            reminder
            for reminder in pending
            if event.completed
            or reminder.owner_id != event.owner_id
            or reminder.event_starts_at != event.starts_at
            or reminder.event_date_only != event.date_only
        ]
        # Release all moving slots before assigning their new times, so reminders
        # can move into one another's old slots without artificial conflicts.
        Reminder.objects.using(using).filter(pk__in=[r.pk for r in changed]).update(
            state=Reminder.State.CANCELLED
        )
        for reminder in changed:
            scheduled = None
            if event.completed:
                reason = "The event was completed."
            elif reminder.owner_id != event.owner_id:
                reason = "The event owner changed."
            elif reminder.relative_minutes is None:
                reason = "The event date changed; this reminder was not relative."
            elif not event.starts_at:
                reason = "The event no longer has an exact start time."
            else:
                try:
                    scheduled = event.starts_at - timedelta(
                        minutes=reminder.relative_minutes
                    )
                except OverflowError:
                    pass
                reason = "The rescheduled reminder time is in the past or invalid."
            if scheduled and scheduled > timezone.now():
                try:
                    with transaction.atomic(using=using):
                        Reminder.objects.using(using).filter(pk=reminder.pk).update(
                            state=Reminder.State.PENDING,
                            scheduled_at=scheduled,
                            event_starts_at=event.starts_at,
                            event_date_only=event.date_only,
                            cancellation_reason="",
                            attempts=0,
                            next_attempt_at=None,
                        )
                    continue
                except IntegrityError:
                    if not (
                        Reminder.objects.using(using)
                        .filter(
                            event=event,
                            scheduled_at=scheduled,
                            state=Reminder.State.PENDING,
                        )
                        .exclude(pk=reminder.pk)
                        .exists()
                    ):
                        raise
                    reason = "Another pending reminder already uses the new time."
            Reminder.objects.using(using).filter(pk=reminder.pk).update(
                cancellation_reason=reason
            )


@receiver(post_save, sender=Task)
def cancel_changed_task_reminders(sender, instance, using, **kwargs):
    with transaction.atomic(using=using):
        task = (
            Task.objects.using(using).select_for_update().filter(pk=instance.pk).first()
        )
        if not task:
            return
        pending = Reminder.objects.using(using).filter(
            task=task, state=Reminder.State.PENDING
        )
        if not task.completed:
            pending = pending.exclude(
                task_due_date=task.due_date, owner_id=task.owner_id
            )
        pending.update(
            state=Reminder.State.CANCELLED,
            cancellation_reason="The task was completed, changed, or its owner changed.",
        )
