from datetime import timedelta

from django import forms
from django.utils import timezone

from core.models import Event, Task

from .models import Reminder


class ReminderForm(forms.Form):
    event = forms.ModelChoiceField(queryset=Event.objects.none(), required=False)
    task = forms.ModelChoiceField(queryset=Task.objects.none(), required=False)
    minutes_before = forms.IntegerField(
        required=False, min_value=0, max_value=2147483647
    )
    scheduled_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Uses your profile timezone. Choose this or minutes before the event.",
    )

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.fields["event"].queryset = Event.objects.filter(
            owner=owner, completed=False
        )
        self.fields["task"].queryset = Task.objects.filter(owner=owner, completed=False)

    def clean(self):
        data = super().clean()
        event = data.get("event")
        task = data.get("task")
        minutes = data.get("minutes_before")
        scheduled = data.get("scheduled_at")
        if (minutes is None) == (scheduled is None):
            raise forms.ValidationError(
                "Enter either minutes before or an exact reminder time."
            )
        if bool(event) == bool(task):
            raise forms.ValidationError("Choose exactly one event or task.")
        if task and minutes is not None:
            raise forms.ValidationError(
                "Task reminders require an exact reminder time."
            )
        if not event and not task:
            return data
        if minutes is not None:
            if not event.starts_at:
                raise forms.ValidationError(
                    "Minutes before requires an event with an exact start time."
                )
            try:
                scheduled = event.starts_at - timedelta(minutes=minutes)
            except OverflowError as exc:
                raise forms.ValidationError("Minutes before is too large.") from exc
        if scheduled <= timezone.now():
            raise forms.ValidationError("Choose a reminder time in the future.")
        if Reminder.objects.filter(
            event=event, task=task, scheduled_at=scheduled, state=Reminder.State.PENDING
        ).exists():
            raise forms.ValidationError(
                "A reminder already exists for this target and time."
            )
        data["scheduled_at"] = scheduled
        return data
