from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class QuietHoursPreference(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    start_time = models.TimeField(default=time(22, 0))
    end_time = models.TimeField(default=time(7, 0))

    def clean(self):
        super().clean()
        if self.start_time is not None and self.start_time == self.end_time:
            raise ValidationError("Start and end times must be different.")
