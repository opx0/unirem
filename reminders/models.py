from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Reminder(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(
        "core.Event",
        on_delete=models.CASCADE,
        related_name="reminders",
        null=True,
        blank=True,
    )
    task = models.ForeignKey(
        "core.Task",
        on_delete=models.CASCADE,
        related_name="reminders",
        null=True,
        blank=True,
    )
    scheduled_at = models.DateTimeField()
    event_starts_at = models.DateTimeField(null=True, blank=True)
    event_date_only = models.DateField(null=True, blank=True)
    task_due_date = models.DateField(null=True, blank=True)
    state = models.CharField(
        max_length=10, choices=State.choices, default=State.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar = ["-scheduled_at", "-pk"]
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["event", "scheduled_at"], name="reminder_event_time_unique"
            ),
            models.UniqueConstraint(
                fields=["task", "scheduled_at"], name="reminder_task_time_unique"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(event__isnull=False, task__isnull=True)
                    | models.Q(event__isnull=True, task__isnull=False)
                ),
                name="reminder_exactly_one_target",
            ),
        ]
        indexes: ClassVar = [models.Index(fields=["state", "scheduled_at"])]

    def clean(self):
        if bool(self.event_id) == bool(self.task_id):
            raise ValidationError("Choose exactly one event or task.")
        if self.event_id and self.event.owner_id != self.owner_id:
            raise ValidationError("The event must belong to this student.")
        if self.task_id and self.task.owner_id != self.owner_id:
            raise ValidationError("The task must belong to this student.")

    @property
    def target(self):
        return self.event if self.event_id else self.task


class NotificationDelivery(models.Model):
    reminder = models.OneToOneField(
        Reminder, on_delete=models.CASCADE, related_name="delivery"
    )
    delivered_at = models.DateTimeField(auto_now_add=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
