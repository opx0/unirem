from django import forms

from .models import Suggestion


class TextForm(forms.Form):
    text = forms.CharField(
        max_length=1000000,
        widget=forms.Textarea(attrs={"rows": 12}),
        label="Text",
    )


class SuggestionForm(forms.ModelForm):
    kind = forms.ChoiceField(
        choices=[("event", "Event"), ("task", "Task"), ("information", "Information")]
    )

    class Meta:
        model = Suggestion
        fields = ("kind", "title", "description", "date_text")
