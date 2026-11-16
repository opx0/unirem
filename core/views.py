import json
import logging
from pathlib import Path
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.db import transaction
from django.db.models import DateField, F, Q
from django.db.models.functions import Coalesce, TruncDate
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from checklist.models import ChecklistItem
from connections.models import SourceConnection
from intake.models import ExtractionRun, Suggestion
from mail_import.models import ImportedMail
from quiet_hours.models import QuietHoursPreference
from reminders.models import NotificationDelivery, Reminder
from revisions.models import EventChangeProposal, Resolution

from .forms import (
    CaptureForm,
    EventForm,
    NoticeEditForm,
    NoticeFilterForm,
    OpportunityForm,
    ProfileForm,
    RegistrationForm,
    TaskForm,
)
from .models import (
    AuditEvent,
    Event,
    Notice,
    Opportunity,
    OpportunityStage,
    PendingFileDeletion,
    SourceDocument,
    StudentProfile,
    Task,
)

logger = logging.getLogger(__name__)


def mark_relevance_mismatches(notices, profile):
    for notice in notices:
        # Only compare values explicitly supplied on both records.
        notice.relevance_mismatch = bool(
            profile
            and any(
                target.strip()
                and actual.strip()
                and target.strip().casefold() != actual.strip().casefold()
                for target, actual in (
                    (notice.target_program, profile.program),
                    (notice.target_batch, profile.batch),
                )
            )
        )


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("profile")
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile(request):
    instance = StudentProfile.objects.filter(user=request.user).first()
    form = ProfileForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.user = request.user
        item.save()
        messages.success(request, "Profile saved.")
        return redirect("home")
    return render(
        request,
        "core/form.html",
        {"form": form, "heading": "Student profile", "submit": "Save profile"},
    )


@login_required
def home(request):
    today = timezone.localdate()
    profile = StudentProfile.objects.filter(user=request.user).first()
    notices = Notice.objects.filter(owner=request.user).exclude(
        status=Notice.Status.ARCHIVED
    )[:5]
    mark_relevance_mismatches(notices, profile)
    upcoming = (
        Event.objects.filter(owner=request.user, completed=False)
        .filter(Q(date_only__gte=today) | Q(starts_at__gte=timezone.now()))
        .annotate(
            day=Coalesce("date_only", TruncDate("starts_at"), output_field=DateField())
        )
        .order_by("day", "starts_at")[:8]
    )
    return render(
        request,
        "core/home.html",
        {
            "notices": notices,
            "events": upcoming,
            "tasks": Task.objects.filter(owner=request.user, completed=False).order_by(
                F("due_date").asc(nulls_last=True)
            )[:8],
            "profile_missing": profile is None,
            "recent_deliveries": NotificationDelivery.objects.filter(
                reminder__owner=request.user, dismissed_at__isnull=True
            )
            .select_related("reminder__event")
            .order_by("-delivered_at")[:5],
        },
    )


@login_required
def inbox(request):
    if request.method == "POST":
        pk = request.POST.get("notice_id", "")
        if not pk.isdecimal() or request.POST.get("state") not in ("read", "unread"):
            raise Http404
        notice = get_object_or_404(Notice, owner=request.user, pk=pk)
        notice.is_read = request.POST["state"] == "read"
        notice.save(update_fields=["is_read"])
        url = request.path
        if request.GET:
            url += "?" + request.GET.urlencode()
        return redirect(url)
    form = NoticeFilterForm(request.GET)
    qs = Notice.objects.filter(owner=request.user).select_related("document")
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            qs = qs.filter(
                Q(title__icontains=data["q"])
                | Q(summary__icontains=data["q"])
                | Q(original_text__icontains=data["q"])
            )
        if data["status"]:
            qs = qs.filter(status=data["status"])
        if data.get("source_context"):
            qs = qs.filter(source_context=data["source_context"])
        if data["category"]:
            qs = qs.filter(category=data["category"])
        if data["state"]:
            qs = qs.filter(is_read=data["state"] == "read")
    mark_relevance_mismatches(
        qs, StudentProfile.objects.filter(user=request.user).first()
    )
    return render(
        request,
        "core/_items.html"
        if request.headers.get("HX-Request") == "true"
        else "core/list.html",
        {"heading": "Inbox", "items": qs, "kind": "notice", "filter_form": form},
    )


@login_required
def capture(request):
    form = CaptureForm(request.POST or None, request.FILES or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        document = None
        try:
            with transaction.atomic():
                notice = form.save(commit=False)
                notice.owner = request.user
                upload = form.cleaned_data.get("upload")
                if upload:
                    document = SourceDocument(
                        owner=request.user,
                        file=upload,
                        original_name=Path(upload.name).name[:255],
                        sha256=form.upload_digest,
                    )
                    document.save()
                    notice.document = document
                notice.save()
                AuditEvent.objects.create(
                    owner=request.user,
                    notice=notice,
                    action="captured",
                    detail={"status": notice.status},
                )
        except Exception:
            if document and document.file._committed and document.file.name:
                try:
                    document.file.storage.delete(document.file.name)
                except Exception:
                    PendingFileDeletion.objects.get_or_create(name=document.file.name)
                    logger.exception("Failed to delete captured file; queued for retry")
            raise
        messages.success(
            request, "Captured. Review the original and add each action separately."
        )
        return redirect("notice", pk=notice.pk)
    return render(
        request,
        "core/form.html",
        {
            "form": form,
            "heading": "Capture a notice",
            "submit": "Save for review",
            "multipart": True,
        },
    )


@login_required
def notice_detail(request, pk):
    notice = get_object_or_404(
        Notice.objects.filter(owner=request.user).select_related("document"), pk=pk
    )
    if request.method == "GET" and not notice.is_read:
        Notice.objects.filter(pk=notice.pk, owner=request.user, is_read=False).update(
            is_read=True
        )
        notice.is_read = True
    mark_relevance_mismatches(
        [notice], StudentProfile.objects.filter(user=request.user).first()
    )
    return render(
        request,
        "core/notice.html",
        {
            "notice": notice,
            "history": notice.history.order_by("-created_at"),
            "events": notice.events.all(),
            "tasks": notice.tasks.all(),
            "opportunities": notice.opportunities.all(),
        },
    )


@login_required
def notice_edit(request, pk):
    notice = get_object_or_404(Notice, owner=request.user, pk=pk)
    original = {field: getattr(notice, field) for field in NoticeEditForm.Meta.fields}
    form = NoticeEditForm(request.POST or None, instance=notice)
    if request.method == "POST" and form.is_valid():
        before = {field: original[field] for field in form.changed_data}
        with transaction.atomic():
            form.save()
            if before:
                AuditEvent.objects.create(
                    owner=request.user,
                    notice=notice,
                    action="corrected",
                    detail={
                        "before": before,
                        "after": {field: getattr(notice, field) for field in before},
                    },
                )
        messages.success(request, "Notice updated; original evidence was preserved.")
        return redirect("notice", pk=pk)
    return render(
        request,
        "core/form.html",
        {"form": form, "heading": "Review notice", "submit": "Save changes"},
    )


@login_required
def document_preview(request, pk):
    document = get_object_or_404(SourceDocument, owner=request.user, pk=pk)
    ext = Path(document.original_name).suffix.lower()
    content_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    content_type = content_types.get(ext)
    if not content_type:
        raise Http404("Preview is only available for images.")
    try:
        response = FileResponse(
            document.file.open("rb"),
            content_type=content_type,
        )
    except (FileNotFoundError, OSError) as exc:
        raise Http404("Source file is unavailable") from exc
    response["Cache-Control"] = "private, no-store"
    response["Content-Security-Policy"] = "default-src 'none'"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def document_download(request, pk):
    document = get_object_or_404(SourceDocument, owner=request.user, pk=pk)
    try:
        response = FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=document.original_name,
        )
    except (FileNotFoundError, OSError) as exc:
        raise Http404("Source file is unavailable") from exc
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def records(request, kind):
    mapping = {
        "events": (Event, "Events"),
        "tasks": (Task, "Tasks"),
        "opportunities": (Opportunity, "Opportunities"),
    }
    if kind not in mapping:
        raise Http404
    model, heading = mapping[kind]
    items = model.objects.filter(owner=request.user)
    if kind == "events":
        items = items.order_by("date_only", "starts_at")
    return render(
        request, "core/list.html", {"heading": heading, "items": items, "kind": kind}
    )


@login_required
def record_form(request, kind, pk=None):
    mapping = {
        "events": (Event, EventForm),
        "tasks": (Task, TaskForm),
        "opportunities": (Opportunity, OpportunityForm),
    }
    if kind not in mapping:
        raise Http404
    model, form_type = mapping[kind]
    instance = get_object_or_404(model, owner=request.user, pk=pk) if pk else None
    old_stage = instance.stage if isinstance(instance, Opportunity) else ""
    form = form_type(request.POST or None, instance=instance, owner=request.user)
    form.instance.owner = request.user
    if not pk and not request.POST:
        notice_id = request.GET.get("notice")
        if (
            notice_id
            and Notice.objects.filter(owner=request.user, pk=notice_id).exists()
        ):
            form.fields["notice"].initial = notice_id
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.full_clean()
        with transaction.atomic():
            item.save()
            if isinstance(item, Opportunity) and item.stage != old_stage:
                OpportunityStage.objects.create(
                    owner=request.user,
                    opportunity=item,
                    stage=item.stage,
                    previous_stage=old_stage,
                )
        messages.success(request, f"{model.__name__} saved.")
        return redirect(kind)
    return render(
        request,
        "core/form.html",
        {
            "form": form,
            "heading": f"{'Edit' if pk else 'New'} {model.__name__.lower()}",
            "submit": "Save",
            "stage_history": instance.stage_history.all()
            if isinstance(instance, Opportunity)
            else None,
        },
    )


@login_required
@require_POST
def toggle_task(request, pk):
    task = get_object_or_404(Task, owner=request.user, pk=pk)
    task.completed = not task.completed
    task.save(update_fields=["completed"])
    return redirect("tasks")


@login_required
def privacy(request):
    return render(request, "core/privacy.html")


@login_required
@require_POST
def export_data(request):
    archive = SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b")  # noqa: SIM115 -- FileResponse closes the stream.
    models = (
        Notice,
        SourceDocument,
        Opportunity,
        OpportunityStage,
        Event,
        Task,
        AuditEvent,
        ExtractionRun,
        Reminder,
        Resolution,
        EventChangeProposal,
        SourceConnection,
        QuietHoursPreference,
        ImportedMail,
    )
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        bundle.writestr(
            "account.json",
            json.dumps(
                {"username": request.user.get_username(), "email": request.user.email}
            ),
        )
        for model in models:
            bundle.writestr(
                f"{model._meta.model_name}.json",
                serializers.serialize("json", model.objects.filter(owner=request.user)),
            )
        bundle.writestr(
            "notificationdelivery.json",
            serializers.serialize(
                "json",
                NotificationDelivery.objects.filter(reminder__owner=request.user),
            ),
        )
        bundle.writestr(
            "suggestion.json",
            serializers.serialize(
                "json", Suggestion.objects.filter(run__owner=request.user)
            ),
        )
        bundle.writestr(
            "checklist.json",
            serializers.serialize(
                "json", ChecklistItem.objects.filter(task__owner=request.user)
            ),
        )
        profiles = StudentProfile.objects.filter(user=request.user)
        bundle.writestr("profile.json", serializers.serialize("json", profiles))
        missing = []
        for document in SourceDocument.objects.filter(owner=request.user):
            try:
                with (
                    document.file.open("rb") as source,
                    bundle.open(
                        f"documents/{document.pk}{Path(document.file.name).suffix}", "w"
                    ) as destination,
                ):
                    while chunk := source.read(1024 * 1024):
                        destination.write(chunk)
            except OSError:
                missing.append(document.pk)
        bundle.writestr("missing_documents.json", json.dumps(missing))
    archive.seek(0)
    response = FileResponse(
        archive, as_attachment=True, filename="campus-radar-export.zip"
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def delete_account(request):
    if request.method == "POST":
        if not authenticate(
            request,
            username=request.user.get_username(),
            password=request.POST.get("password", ""),
        ):
            messages.error(request, "Incorrect password; nothing was deleted.")
        elif request.POST.get("confirmation") != "DELETE":
            messages.error(request, "Type DELETE to confirm; nothing was deleted.")
        else:
            user = request.user
            with transaction.atomic():
                user.delete()
            logout(request)
            messages.success(
                request,
                "Your account and records were deleted. Uploaded files are queued for deletion by the maintenance worker.",
            )
            return redirect("login")
    return render(request, "core/delete_account.html")
