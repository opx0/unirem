from pathlib import Path

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import DateField, F, Q
from django.db.models.functions import Coalesce, TruncDate
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    CaptureForm,
    EventForm,
    NoticeEditForm,
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
    SourceDocument,
    StudentProfile,
    Task,
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
            "notices": Notice.objects.filter(owner=request.user).exclude(
                status=Notice.Status.ARCHIVED
            )[:5],
            "events": upcoming,
            "tasks": Task.objects.filter(owner=request.user, completed=False).order_by(
                F("due_date").asc(nulls_last=True)
            )[:8],
            "profile_missing": not StudentProfile.objects.filter(
                user=request.user
            ).exists(),
        },
    )


@login_required
def inbox(request):
    status = request.GET.get("status", "")
    qs = Notice.objects.filter(owner=request.user).select_related("document")
    if status in Notice.Status.values:
        qs = qs.filter(status=status)
    return render(
        request,
        "core/_items.html"
        if request.headers.get("HX-Request") == "true"
        else "core/list.html",
        {"heading": "Inbox", "items": qs, "kind": "notice", "status": status},
    )


@login_required
def capture(request):
    form = CaptureForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            notice = form.save(commit=False)
            notice.owner = request.user
            upload = form.cleaned_data.get("upload")
            if upload:
                document = SourceDocument.objects.create(
                    owner=request.user,
                    file=upload,
                    original_name=Path(upload.name).name[:255],
                )
                notice.document = document
            notice.save()
            AuditEvent.objects.create(
                owner=request.user,
                notice=notice,
                action="captured",
                detail={"status": notice.status},
            )
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
    form = NoticeEditForm(request.POST or None, instance=notice)
    if request.method == "POST" and form.is_valid():
        before = {field: getattr(notice, field) for field in form.changed_data}
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
        item.save()
        messages.success(request, f"{model.__name__} saved.")
        return redirect(kind)
    return render(
        request,
        "core/form.html",
        {
            "form": form,
            "heading": f"{'Edit' if pk else 'New'} {model.__name__.lower()}",
            "submit": "Save",
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
def search(request):
    query = request.GET.get("q", "").strip()[:200]
    results = {}
    if query:
        results = {
            "notices": Notice.objects.filter(owner=request.user).filter(
                Q(title__icontains=query)
                | Q(original_text__icontains=query)
                | Q(summary__icontains=query)
            ),
            "events": Event.objects.filter(owner=request.user, title__icontains=query),
            "tasks": Task.objects.filter(owner=request.user).filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            ),
            "opportunities": Opportunity.objects.filter(owner=request.user).filter(
                Q(title__icontains=query) | Q(notes__icontains=query)
            ),
        }
    return render(request, "core/search.html", {"query": query, "results": results})
