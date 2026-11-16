from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .forms import QuestionForm
from .services import answer_question


@login_required
def ask(request):
    form = QuestionForm(request.GET or None)
    results = []
    truncated = False
    searched = form.is_valid()
    if searched:
        results, truncated = answer_question(
            request.user, form.cleaned_data["question"]
        )
    return render(
        request,
        "answers/ask.html",
        {
            "form": form,
            "results": results,
            "searched": searched,
            "truncated": truncated,
        },
    )
