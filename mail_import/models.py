from django.conf import settings
from django.db import models


class ImportedMail(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notice = models.OneToOneField("core.Notice", on_delete=models.CASCADE)
    run = models.OneToOneField("intake.ExtractionRun", on_delete=models.CASCADE)
    original_name = models.CharField(max_length=255)
    source = models.BinaryField()
    sender = models.TextField(blank=True)
    subject = models.TextField(blank=True)
    date_header = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
