import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction
from django.db.models import F, Q
from django.utils import timezone

from core.models import Event, Task
from quiet_hours.services import defer_until
from reminders.models import NotificationDelivery, Reminder

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deliver due in-app reminders in one pass."

    def handle(self, *args, **options):
        now = timezone.now()
        ids = list(
            Reminder.objects.filter(state=Reminder.State.PENDING, scheduled_at__lte=now)
            .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
            .order_by("scheduled_at", "pk")
            .values_list(
                "pk",
                "event_id",
                "task_id",
                "scheduled_at",
                "attempts",
                "next_attempt_at",
            )
        )
        delivered = 0
        failed = 0
        for pk, event_id, task_id, scheduled_at, attempts, next_attempt_at in ids:
            try:
                was_delivered = False
                with transaction.atomic():
                    # Lock the target before updating its reminder, as target writers do.
                    model = Event if event_id else Task
                    target_id = event_id or task_id
                    if (
                        not model.objects.select_for_update()
                        .filter(pk=target_id)
                        .exists()
                    ):
                        continue
                    pending = Reminder.objects.filter(
                        pk=pk, state=Reminder.State.PENDING, scheduled_at__lte=now
                    ).filter(
                        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)
                    )
                    if event_id:
                        valid = pending.filter(
                            event__completed=False,
                            event__owner_id=F("owner_id"),
                        ).filter(
                            Q(event_starts_at=F("event__starts_at"))
                            | Q(
                                event_starts_at__isnull=True,
                                event__starts_at__isnull=True,
                            ),
                            Q(event_date_only=F("event__date_only"))
                            | Q(
                                event_date_only__isnull=True,
                                event__date_only__isnull=True,
                            ),
                        )
                    else:
                        valid = pending.filter(
                            task__completed=False, task__owner_id=F("owner_id")
                        ).filter(
                            Q(task_due_date=F("task__due_date"))
                            | Q(task_due_date__isnull=True, task__due_date__isnull=True)
                        )
                    reminder = valid.select_related("owner").first()
                    deferred = defer_until(reminder.owner, now) if reminder else None
                    if deferred:
                        valid.update(next_attempt_at=deferred)
                    elif valid.update(state=Reminder.State.DELIVERED):
                        NotificationDelivery.objects.get_or_create(reminder_id=pk)
                        was_delivered = True
                    else:
                        pending.update(
                            state=Reminder.State.CANCELLED,
                            cancellation_reason="The target was completed, changed, or no longer belongs to you.",
                        )
                delivered += was_delivered
            except Exception:
                failed += 1
                logger.exception("Could not deliver reminder %s.", pk)
                try:
                    delay = min(2 ** min(attempts, 8), 60)
                    Reminder.objects.filter(
                        pk=pk,
                        state=Reminder.State.PENDING,
                        scheduled_at=scheduled_at,
                        attempts=attempts,
                        next_attempt_at=next_attempt_at,
                    ).update(
                        attempts=F("attempts") + 1,
                        next_attempt_at=timezone.now() + timedelta(minutes=delay),
                    )
                except DatabaseError:
                    logger.exception("Could not record retry for reminder %s.", pk)
        self.stdout.write(
            f"Delivered {delivered} in-app reminder(s); {failed} delivery attempt(s) failed."
        )
