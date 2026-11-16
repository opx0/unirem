import hashlib
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods

from core.models import Event, Notice

from .forms import ComparisonForm, EventChangeForm, ResolutionForm
from .models import EventChangeProposal, Resolution


def source_snapshot(notice):
    document = notice.document
    return {
        "id": notice.pk,
        "title": notice.title,
        "original_text": notice.original_text,
        "summary": notice.summary,
        "document_id": document.pk
        if document and document.owner_id == notice.owner_id
        else None,
        "document_name": document.original_name
        if document and document.owner_id == notice.owner_id
        else "",
    }


def comparison_token(first, second, owner):
    data = json.dumps([source_snapshot(first), source_snapshot(second)], sort_keys=True)
    digest = hashlib.sha256(data.encode()).hexdigest()
    return signing.dumps(
        {"owner": owner.pk, "digest": digest}, salt="revisions.comparison"
    )


def event_snapshot(event):
    return {
        "starts_at": event.starts_at.isoformat() if event.starts_at else None,
        "ends_at": event.ends_at.isoformat() if event.ends_at else None,
        "date_only": event.date_only.isoformat() if event.date_only else None,
        "location": event.location,
    }


@login_required
@require_http_methods(["GET"])
def index(request):
    form = ComparisonForm(request.GET or None, owner=request.user)
    if form.is_bound and form.is_valid():
        return redirect(
            "revisions:compare",
            first_pk=form.cleaned_data["first"].pk,
            second_pk=form.cleaned_data["second"].pk,
        )
    return render(request, "revisions/index.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def compare(request, first_pk, second_pk):
    if first_pk == second_pk:
        raise Http404
    notices = Notice.objects.filter(owner=request.user).select_related("document")
    first = get_object_or_404(notices, pk=first_pk)
    second = get_object_or_404(notices, pk=second_pk)
    form = ResolutionForm(
        request.POST or None,
        initial={"comparison": comparison_token(first, second, request.user)},
    )
    if request.method == "POST" and form.is_valid():
        try:
            token = signing.loads(
                form.cleaned_data["comparison"], salt="revisions.comparison"
            )
        except signing.BadSignature:
            token = None
        with transaction.atomic():
            # Lock in a stable order so simultaneous comparisons cannot overwrite a decision.
            locked = {
                notice.pk: notice
                for notice in Notice.objects.filter(
                    owner=request.user, pk__in=[first_pk, second_pk]
                )
                .order_by("pk")
                .select_for_update()
            }
            if len(locked) != 2:
                raise Http404
            first, second = locked[first_pk], locked[second_pk]
            expected = signing.loads(
                comparison_token(first, second, request.user),
                salt="revisions.comparison",
            )
            if token != expected:
                form.add_error(
                    None, "The comparison has changed. Reload it before deciding."
                )
            else:
                before = first.summary
                after = (
                    form.cleaned_data["summary"]
                    if form.cleaned_data["decision"]
                    == Resolution.Decision.UPDATE_SUMMARY
                    else before
                )
                Resolution.objects.create(
                    owner=request.user,
                    first_notice=first,
                    second_notice=second,
                    decision=form.cleaned_data["decision"],
                    first_source=source_snapshot(first),
                    second_source=source_snapshot(second),
                    summary_before=before,
                    summary_after=after,
                )
                if form.cleaned_data["decision"] == Resolution.Decision.UPDATE_SUMMARY:
                    first.summary = after
                    first.save(update_fields=["summary", "updated_at"])
                messages.success(
                    request,
                    "Your decision was recorded. No events or sources were changed.",
                )
                return redirect(
                    "revisions:compare", first_pk=first_pk, second_pk=second_pk
                )
    return render(
        request,
        "revisions/compare.html",
        {
            "first": first,
            "second": second,
            "form": form,
            "proposals": EventChangeProposal.objects.filter(
                owner=request.user, first_notice=first, second_notice=second
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def propose_event_change(request, first_pk, second_pk):
    if first_pk == second_pk:
        raise Http404
    notices = Notice.objects.filter(owner=request.user).select_related("document")
    first = get_object_or_404(notices, pk=first_pk)
    second = get_object_or_404(notices, pk=second_pk)
    form = EventChangeForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = {
                n.pk: n
                for n in Notice.objects.filter(
                    owner=request.user, pk__in=[first_pk, second_pk]
                )
                .order_by("pk")
                .select_for_update()
            }
            if len(locked) != 2:
                raise Http404
            event = get_object_or_404(
                Event.objects.select_for_update(),
                pk=form.cleaned_data["event"].pk,
                owner=request.user,
            )
            proposal = EventChangeProposal.objects.create(
                owner=request.user,
                event=event,
                first_notice=locked[first_pk],
                second_notice=locked[second_pk],
                first_source=source_snapshot(locked[first_pk]),
                second_source=source_snapshot(locked[second_pk]),
                event_before=event_snapshot(event),
                event_after={
                    key: value.isoformat() if value and key != "location" else value
                    for key, value in form.cleaned_data.items()
                    if key != "event"
                },
            )
        return redirect("revisions:event_change", pk=proposal.pk)
    return render(
        request,
        "revisions/propose_event_change.html",
        {"form": form, "first": first, "second": second},
    )


@login_required
@require_http_methods(["GET", "POST"])
def event_change(request, pk):
    proposal = get_object_or_404(EventChangeProposal, pk=pk, owner=request.user)
    if request.method == "POST":
        with transaction.atomic():
            proposal = get_object_or_404(
                EventChangeProposal.objects.select_for_update(),
                pk=pk,
                owner=request.user,
            )
            notices = {
                n.pk: n
                for n in Notice.objects.filter(
                    owner=request.user,
                    pk__in=[proposal.first_notice_id, proposal.second_notice_id],
                )
                .order_by("pk")
                .select_for_update()
            }
            event = (
                Event.objects.select_for_update()
                .filter(pk=proposal.event_id, owner=request.user)
                .first()
            )
            if proposal.accepted_at:
                messages.error(request, "This proposal has already been accepted.")
            elif (
                event is None
                or len(notices) != 2
                or source_snapshot(notices[proposal.first_notice_id])
                != proposal.first_source
                or source_snapshot(notices[proposal.second_notice_id])
                != proposal.second_source
                or event_snapshot(event) != proposal.event_before
            ):
                messages.error(
                    request, "The event or sources have changed. Create a new proposal."
                )
            else:
                after = proposal.event_after
                event.starts_at = (
                    parse_datetime(after["starts_at"]) if after["starts_at"] else None
                )
                event.ends_at = (
                    parse_datetime(after["ends_at"]) if after["ends_at"] else None
                )
                event.date_only = (
                    parse_date(after["date_only"]) if after["date_only"] else None
                )
                event.location = after["location"]
                event.save(
                    update_fields=["starts_at", "ends_at", "date_only", "location"]
                )
                proposal.accepted_at = timezone.now()
                proposal.save(update_fields=["accepted_at"])
                messages.success(request, "Event change accepted.")
            return redirect("revisions:event_change", pk=pk)
    return render(request, "revisions/event_change.html", {"proposal": proposal})
