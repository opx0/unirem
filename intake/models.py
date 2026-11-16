from django.conf import settings
from django.db import models


class ExtractionRun(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Text available"
        FAILED = "failed", "Failed"

    class Source(models.TextChoices):
        DOCUMENT = "document", "Document extraction"
        MANUAL = "manual", "Manual transcription"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notice = models.ForeignKey(
        "core.Notice", on_delete=models.CASCADE, related_name="extraction_runs"
    )
    source = models.CharField(max_length=10, choices=Source.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    extracted_text = models.TextField(blank=True)
    reviewed_text = models.TextField(blank=True)
    text_hash = models.CharField(max_length=64, blank=True, db_index=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")


class Suggestion(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Needs review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    run = models.ForeignKey(
        ExtractionRun, on_delete=models.CASCADE, related_name="suggestions"
    )
    source_text = models.TextField()
    evidence = models.TextField()
    kind = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date_text = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
