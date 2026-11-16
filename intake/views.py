from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import EventForm, TaskForm
from core.models import Notice

from .forms import SuggestionForm, TextForm
from .models import ExtractionRun, Suggestion
from .services import ai_suggestions, extract_document, local_suggestions, text_hash


@login_required
def review(request, pk):
    notice = get_object_or_404(
        Notice.objects.select_related("document"), pk=pk, owner=request.user
    )
    runs = list(
        ExtractionRun.objects.filter(
            owner=request.user, notice=notice
        ).prefetch_related("suggestions")
    )
    for run in runs:
        run.duplicates = (
            ExtractionRun.objects.filter(
                owner=request.user, notice__owner=request.user, text_hash=run.text_hash
            )
            .exclude(notice=notice)
            .select_related("notice")
            if run.text_hash
            else []
        )
    return render(
        request,
        "intake/review.html",
        {"notice": notice, "runs": runs, "manual_form": TextForm()},
    )


@login_required
@require_POST
def extract(request, pk):
    notice = get_object_or_404(
        Notice.objects.select_related("document"), pk=pk, owner=request.user
    )
    if notice.document and notice.document.owner_id != request.user.pk:
        text, failure = "", "The attached document is unavailable."
    else:
        text, failure = extract_document(notice.document)
    ExtractionRun.objects.create(
        owner=request.user,
        notice=notice,
        source=ExtractionRun.Source.DOCUMENT,
        status=ExtractionRun.Status.FAILED if failure else ExtractionRun.Status.SUCCESS,
        extracted_text=text,
        reviewed_text=text,
        text_hash=text_hash(text),
        failure_reason=failure,
    )
    return redirect("intake:review", pk=pk)


@login_required
@require_POST
def manual(request, pk):
    notice = get_object_or_404(Notice, pk=pk, owner=request.user)
    form = TextForm(request.POST)
    if form.is_valid():
        text = form.cleaned_data["text"]
        ExtractionRun.objects.create(
            owner=request.user,
            notice=notice,
            source=ExtractionRun.Source.MANUAL,
            status=ExtractionRun.Status.SUCCESS,
            extracted_text=text,
            reviewed_text=text,
            text_hash=text_hash(text),
        )
        return redirect("intake:review", pk=pk)
    runs = ExtractionRun.objects.filter(owner=request.user, notice=notice)
    return render(
        request,
        "intake/review.html",
        {"notice": notice, "runs": runs, "manual_form": form},
    )


@login_required
def edit(request, pk, run_pk):
    notice = get_object_or_404(Notice, pk=pk, owner=request.user)
    run = get_object_or_404(
        ExtractionRun,
        pk=run_pk,
        notice=notice,
        owner=request.user,
        status=ExtractionRun.Status.SUCCESS,
    )
    form = TextForm(request.POST or None, initial={"text": run.reviewed_text})
    if request.method == "POST" and form.is_valid():
        run.reviewed_text = form.cleaned_data["text"]
        run.save(update_fields=["reviewed_text"])
        messages.success(
            request, "Reviewed text saved; the original text is unchanged."
        )
        return redirect("intake:review", pk=pk)
    return render(request, "intake/edit.html", {"notice": notice, "form": form})


@login_required
@require_POST
def suggest(request, pk, run_pk):
    run = get_object_or_404(
        ExtractionRun,
        pk=run_pk,
        notice_id=pk,
        notice__owner=request.user,
        owner=request.user,
        status=ExtractionRun.Status.SUCCESS,
    )
    source = run.reviewed_text
    if not source.strip():
        messages.error(request, "There is no reviewed text to analyze.")
        return redirect("intake:review", pk=pk)
    try:
        items = (
            ai_suggestions(source)
            if request.POST.get("provider") == "ai"
            else local_suggestions(source)
        )
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        with transaction.atomic():
            locked = ExtractionRun.objects.select_for_update().get(
                pk=run.pk, owner=request.user
            )
            if locked.reviewed_text != source:
                messages.error(
                    request, "The source changed during extraction. Please try again."
                )
                return redirect("intake:review", pk=pk)
            count = 0
            for item in items:
                if not Suggestion.objects.filter(
                    run=locked,
                    source_text=source,
                    evidence=item["evidence"],
                    kind=item["kind"],
                ).exists():
                    Suggestion.objects.create(run=locked, source_text=source, **item)
                    count += 1
        messages.success(
            request,
            f"{count} new suggestions created for review. Nothing was scheduled.",
        )
    return redirect("intake:review", pk=pk)


@login_required
def review_suggestion(request, pk, suggestion_pk):
    suggestion = get_object_or_404(
        Suggestion,
        pk=suggestion_pk,
        run__notice_id=pk,
        run__notice__owner=request.user,
        run__owner=request.user,
    )
    if suggestion.status != Suggestion.Status.PENDING:
        return redirect("intake:review", pk=pk)
    form = SuggestionForm(request.POST or None, instance=suggestion)
    if request.method == "POST":
        if request.POST.get("action") == "reject":
            suggestion.status = Suggestion.Status.REJECTED
            suggestion.save(update_fields=["status"])
            return redirect("intake:review", pk=pk)
        if request.POST.get("action") == "approve" and form.is_valid():
            suggestion = form.save(commit=False)
            suggestion.status = Suggestion.Status.APPROVED
            suggestion.save()
            messages.success(
                request, "Suggestion approved for reference. Nothing was scheduled."
            )
            return redirect("intake:review", pk=pk)
    return render(
        request,
        "intake/suggestion.html",
        {"suggestion": suggestion, "form": form, "notice": suggestion.run.notice},
    )


@login_required
def convert_suggestion(request, pk, suggestion_pk):
    suggestion = get_object_or_404(
        Suggestion,
        pk=suggestion_pk,
        run__notice_id=pk,
        run__notice__owner=request.user,
        run__owner=request.user,
        status=Suggestion.Status.APPROVED,
        kind__in=("event", "task"),
    )
    if suggestion.converted_at:
        messages.info(request, "This suggestion has already been converted.")
        return redirect("intake:review", pk=pk)

    form_type = EventForm if suggestion.kind == "event" else TaskForm
    initial = {"title": suggestion.title, "notice": suggestion.run.notice_id}
    if suggestion.kind == "task":
        initial["description"] = suggestion.description
    form = form_type(request.POST or None, owner=request.user, initial=initial)
    form.instance.owner = request.user
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Claim the suggestion before saving, so concurrent submissions cannot duplicate it.
            claimed = Suggestion.objects.filter(
                pk=suggestion.pk,
                run__owner=request.user,
                run__notice__owner=request.user,
                status=Suggestion.Status.APPROVED,
                kind=suggestion.kind,
                converted_at__isnull=True,
            ).update(converted_at=timezone.now())
            if claimed:
                form.save()
        if claimed:
            messages.success(request, f"{suggestion.kind.title()} saved.")
        else:
            messages.info(request, "This suggestion has already been converted.")
        return redirect("intake:review", pk=pk)
    return render(
        request,
        "intake/convert.html",
        {"form": form, "suggestion": suggestion, "notice": suggestion.run.notice},
    )
