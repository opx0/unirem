import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


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
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")

    def __str__(self):
        return f"{self.user}: {self.institution}"


class SourceDocument(Owned):
    file = models.FileField(upload_to=private_path)
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name


class Notice(Owned):
    class Status(models.TextChoices):
        REVIEW = "review", "Needs review"
        CONFIRMED = "confirmed", "Confirmed"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200)
    original_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)
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
