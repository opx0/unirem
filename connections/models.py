from django.conf import settings
from django.db import models


class SourceConnection(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.CharField(max_length=20, choices=Source.choices)
    connected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["owner", "source"], name="unique_owner_source_connection"
            ),
            models.CheckConstraint(
                condition=models.Q(source="manual"), name="connection_manual_only"
            ),
        )
