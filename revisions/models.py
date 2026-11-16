from django.conf import settings
from django.db import models


class Resolution(models.Model):
    class Decision(models.TextChoices):
        KEEP_SEPARATE = "keep_separate", "Keep separately"
        UPDATE_SUMMARY = "update_summary", "Update first notice summary"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    first_notice = models.ForeignKey(
        "core.Notice",
        null=True,
        on_delete=models.SET_NULL,
        related_name="first_resolutions",
    )
    second_notice = models.ForeignKey(
        "core.Notice",
        null=True,
        on_delete=models.SET_NULL,
        related_name="second_resolutions",
    )
    decision = models.CharField(max_length=20, choices=Decision.choices)
    first_source = models.JSONField()
    second_source = models.JSONField()
    summary_before = models.TextField(blank=True)
    summary_after = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")


class EventChangeProposal(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey("core.Event", null=True, on_delete=models.SET_NULL)
    first_notice = models.ForeignKey(
        "core.Notice",
        null=True,
        on_delete=models.SET_NULL,
        related_name="first_event_proposals",
    )
    second_notice = models.ForeignKey(
        "core.Notice",
        null=True,
        on_delete=models.SET_NULL,
        related_name="second_event_proposals",
    )
    first_source = models.JSONField()
    second_source = models.JSONField()
    event_before = models.JSONField()
    event_after = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
