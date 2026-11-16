from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from core.models import Notice
from intake.models import ExtractionRun
from intake.services import text_hash

from .forms import MailImportForm
from .models import ImportedMail


@login_required
def import_mail(request):
    form = MailImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        data = form.parsed_mail
        text = data["text"]
        with transaction.atomic():
            notice = Notice.objects.create(
                owner=request.user,
                title=data["subject"][:200] or "Imported email",
                original_text=text,
            )
            run = ExtractionRun.objects.create(
                owner=request.user,
                notice=notice,
                source=ExtractionRun.Source.MANUAL,
                status=ExtractionRun.Status.SUCCESS,
                extracted_text=text,
                reviewed_text=text,
                text_hash=text_hash(text),
            )
            mail = ImportedMail.objects.create(
                owner=request.user,
                notice=notice,
                run=run,
                original_name=Path(form.cleaned_data["file"].name).name[:255],
                source=form.raw_mail,
                sender=data["sender"],
                subject=data["subject"],
                date_header=data["date_header"],
                sent_at=data["sent_at"],
            )
        return redirect("mail_import:detail", pk=mail.pk)
    return render(request, "mail_import/import.html", {"form": form})


@login_required
@require_GET
def detail(request, pk):
    mail = get_object_or_404(
        ImportedMail,
        pk=pk,
        owner=request.user,
        notice__owner=request.user,
        run__owner=request.user,
    )
    return render(request, "mail_import/detail.html", {"mail": mail})


@login_required
@require_GET
def source(request, pk):
    mail = get_object_or_404(
        ImportedMail,
        pk=pk,
        owner=request.user,
        notice__owner=request.user,
        run__owner=request.user,
    )
    response = HttpResponse(bytes(mail.source), content_type="application/octet-stream")
    response.headers["Content-Disposition"] = (
        'attachment; filename="imported-email.eml"'
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response
