from django import forms


class QuestionForm(forms.Form):
    question = forms.CharField(
        max_length=200,
        label="Your question",
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. When is the placement deadline?"}
        ),
    )
