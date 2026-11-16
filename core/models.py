import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, router, transaction
from django.db.models import Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver


def private_path(instance, filename):
    return f"documents/{instance.owner_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class Owned(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    institution = models.CharField(max_length=160)
    program = models.CharField(max_length=120)
    batch = models.CharField(max_length=60)
    section = models.CharField(max_length=60, blank=True)
    interests = models.TextField(blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")

    def __str__(self):
        return f"{self.user}: {self.institution}"


class SourceDocument(Owned):
    file = models.FileField(upload_to=private_path)
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)

    def __str__(self):
        return self.original_name


class PendingFileDeletion(models.Model):
    name = models.CharField(max_length=500, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


@receiver(pre_delete, sender=SourceDocument)
def queue_document_file_deletion(sender, instance, using, **kwargs):
    if instance.file.name:
        PendingFileDeletion.objects.using(using).get_or_create(name=instance.file.name)


class Notice(Owned):
    class Status(models.TextChoices):
        REVIEW = "review", "Needs review"
        CONFIRMED = "confirmed", "Confirmed"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200)
    original_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    target_program = models.CharField(
        max_length=120,
        blank=True,
        help_text="Program explicitly stated in the notice, if any.",
    )
    target_batch = models.CharField(
        max_length=60,
        blank=True,
        help_text="Batch explicitly stated in the notice, if any.",
    )
    category = models.CharField(
        max_length=30,
        choices=[
            (x, x.title())
            for x in (
                "general",
                "placement",
                "exam",
                "coursework",
                "scholarship",
                "training",
            )
        ],
        default="general",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.REVIEW
    )
    is_read = models.BooleanField(default=False)
    document = models.ForeignKey(
        SourceDocument, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.document_id and self.document.owner_id != self.owner_id:
            raise ValidationError("The source must belong to this student.")

    def __str__(self):
        return self.title


class Opportunity(Owned):
    class Stage(models.TextChoices):
        ANNOUNCED = "announced", "Announced"
        ELIGIBLE = "eligible", "Eligible"
        INELIGIBLE = "ineligible", "Ineligible"
        INTERESTED = "interested", "Interested"
        REGISTERED = "registered", "Registered"
        SHORTLISTED = "shortlisted", "Shortlisted"
        ASSESSMENT = "assessment", "Assessment"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        COMPLETED = "completed", "Completed"

    title = models.CharField(max_length=200)
    category = models.CharField(
        max_length=30,
        choices=[
            (x, x.title())
            for x in (
                "placement",
                "internship",
                "scholarship",
                "certification",
                "other",
            )
        ],
        default="placement",
    )
    stage = models.CharField(
        max_length=20, choices=Stage.choices, default=Stage.ANNOUNCED
    )
    notes = models.TextField(blank=True)
    notice = models.ForeignKey(
        Notice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opportunities",
    )

    def clean(self):
        if self.notice_id and self.notice.owner_id != self.owner_id:
            raise ValidationError("The notice must belong to this student.")

    def __str__(self):
        return self.title


class OpportunityStage(Owned):
    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.CASCADE, related_name="stage_history"
    )
    stage = models.CharField(max_length=20, choices=Opportunity.Stage.choices)
    previous_stage = models.CharField(
        max_length=20, choices=Opportunity.Stage.choices, blank=True
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at", "-pk")

    def clean(self):
        if self.opportunity_id and self.opportunity.owner_id != self.owner_id:
            raise ValidationError("The opportunity must belong to this student.")


class Event(Owned):
    class Kind(models.TextChoices):
        ATTEND = "attend", "Attendance"
        DEADLINE = "deadline", "Deadline"
        REPORT = "report", "Reporting time"
        WINDOW = "window", "Availability window"

    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    date_only = models.DateField(null=True, blank=True)
    source_timezone = models.CharField(max_length=64, blank=True)
    location = models.CharField(max_length=255, blank=True)
    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration stated in the source, not an inferred latest start.",
    )
    notice = models.ForeignKey(
        Notice, null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    opportunity = models.ForeignKey(
        Opportunity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    completed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        # Keep the event change and its reminder signal in the same transaction.
        with transaction.atomic(using=using):
            return super().save(*args, **kwargs)

    def clean(self):
        if bool(self.date_only) == bool(self.starts_at):
            raise ValidationError(
                "Enter either a date-only value or an exact start time."
            )
        if self.ends_at and (not self.starts_at or self.ends_at <= self.starts_at):
            raise ValidationError("End must follow the start time.")
        for related in (self.notice, self.opportunity):
            if related and related.owner_id != self.owner_id:
                raise ValidationError("Linked records must belong to this student.")

    def __str__(self):
        return self.title


class Task(Owned):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    priority = models.CharField(
        max_length=8,
        choices=[("low", "Low"), ("normal", "Normal"), ("high", "High")],
        default="normal",
    )
    notice = models.ForeignKey(
        Notice, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks"
    )
    opportunity = models.ForeignKey(
        Opportunity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        # Keep the task change and its reminder signal in the same transaction.
        with transaction.atomic(using=using):
            return super().save(*args, **kwargs)

    def clean(self):
        for related in (self.notice, self.opportunity):
            if related and related.owner_id != self.owner_id:
                raise ValidationError("Linked records must belong to this student.")

    def __str__(self):
        return self.title


class AuditEvent(Owned):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=30)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=~Q(action=""), name="audit_action_present"
            ),
        )
