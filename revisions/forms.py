from django import forms

from core.models import Event, Notice

from .models import Resolution


class ComparisonForm(forms.Form):
    first = forms.ModelChoiceField(queryset=Notice.objects.none(), label="First notice")
    second = forms.ModelChoiceField(
        queryset=Notice.objects.none(), label="Second notice"
    )

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        notices = Notice.objects.filter(owner=owner)
        self.fields["first"].queryset = notices
        self.fields["second"].queryset = notices

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("first") and cleaned.get("first") == cleaned.get("second"):
            raise forms.ValidationError("Choose two different notices.")
        return cleaned


class ResolutionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=Resolution.Decision.choices, widget=forms.RadioSelect
    )
    summary = forms.CharField(
        required=False, widget=forms.Textarea, label="New summary for the first notice"
    )
    comparison = forms.CharField(widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get(
            "decision"
        ) == Resolution.Decision.UPDATE_SUMMARY and not cleaned.get("summary"):
            self.add_error("summary", "Enter the summary to save.")
        return cleaned


class EventChangeForm(forms.Form):
    event = forms.ModelChoiceField(queryset=Event.objects.none())
    starts_at = forms.DateTimeField(required=False, label="New start date and time")
    ends_at = forms.DateTimeField(required=False, label="New end date and time")
    date_only = forms.DateField(required=False, label="New date (if time is unknown)")
    location = forms.CharField(required=False, max_length=255, label="New venue")

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event"].queryset = Event.objects.filter(owner=owner)

    def clean(self):
        cleaned = super().clean()
        starts_at = cleaned.get("starts_at")
        date_only = cleaned.get("date_only")
        ends_at = cleaned.get("ends_at")
        if bool(starts_at) == bool(date_only):
            raise forms.ValidationError("Enter either a date or an exact start time.")
        if ends_at and (not starts_at or ends_at <= starts_at):
            self.add_error("ends_at", "End must follow the start time.")
        return cleaned
