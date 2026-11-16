from typing import ClassVar

from django import forms

from .models import QuietHoursPreference


class QuietHoursForm(forms.ModelForm):
    class Meta:
        model = QuietHoursPreference
        fields = ("enabled", "start_time", "end_time")
        widgets: ClassVar[dict] = {
            "start_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "end_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        }
