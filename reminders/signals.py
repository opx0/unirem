from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Event, Task

from .models import Reminder


@receiver(post_save, sender=Event)
def cancel_changed_event_reminders(sender, instance, **kwargs):
    pending = Reminder.objects.filter(event=instance, state=Reminder.State.PENDING)
    if not instance.completed:
        pending = pending.exclude(
            event_starts_at=instance.starts_at, event_date_only=instance.date_only
        )
    pending.update(state=Reminder.State.CANCELLED)


@receiver(post_save, sender=Task)
def cancel_changed_task_reminders(sender, instance, **kwargs):
    pending = Reminder.objects.filter(task=instance, state=Reminder.State.PENDING)
    if not instance.completed:
        pending = pending.exclude(task_due_date=instance.due_date)
    pending.update(state=Reminder.State.CANCELLED)
