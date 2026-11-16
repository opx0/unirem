import hashlib
import warnings
from typing import ClassVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from PIL import Image, UnidentifiedImageError

from .models import Event, Notice, Opportunity, SourceDocument, StudentProfile, Task


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ("institution", "program", "batch", "section", "interests", "timezone")

    def clean_timezone(self):
        value = self.cleaned_data["timezone"]
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise forms.ValidationError(
                "Enter an IANA timezone, such as Asia/Kolkata."
            ) from exc
        return value


class CaptureForm(forms.ModelForm):
    upload = forms.FileField(
        required=False,
        help_text="PDF, PNG, JPEG or WebP; maximum 10 MB. Files stay private.",
    )
    confirm_duplicate = forms.BooleanField(
        required=False, label="Save even if this is a duplicate"
    )

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.upload_digest = ""

    class Meta:
        model = Notice
        fields = (
            "title",
            "category",
            "original_text",
            "summary",
            "target_program",
            "target_batch",
        )
        widgets: ClassVar[dict] = {
            "original_text": forms.Textarea(
                attrs={"rows": 6, "placeholder": "Paste the original announcement here"}
            ),
            "summary": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_upload(self):
        file = self.cleaned_data.get("upload")
        if not file:
            return file
        if file.size > 10 * 1024 * 1024:
            raise forms.ValidationError("File exceeds 10 MB.")
        header = file.read(16)
        file.seek(0)
        extension = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
        accepted = {
            "pdf": header.startswith(b"%PDF-"),
            "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
            "jpg": header.startswith(b"\xff\xd8\xff"),
            "jpeg": header.startswith(b"\xff\xd8\xff"),
            "webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
        }
        if not accepted.get(extension, False):
            raise forms.ValidationError("Upload a valid PDF, PNG, JPEG or WebP file.")
        if extension != "pdf":
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(file) as image:
                        expected = {
                            "png": "PNG",
                            "jpg": "JPEG",
                            "jpeg": "JPEG",
                            "webp": "WEBP",
                        }
                        if image.format != expected[extension]:
                            raise forms.ValidationError(
                                "Upload a valid PDF, PNG, JPEG or WebP file."
                            )
                        image.verify()
            except (
                UnidentifiedImageError,
                OSError,
                ValueError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
            ) as exc:
                raise forms.ValidationError(
                    "Upload a valid PDF, PNG, JPEG or WebP file."
                ) from exc
            finally:
                file.seek(0)
        position = file.tell()
        try:
            file.seek(0)
            digest = hashlib.sha256()
            for chunk in file.chunks():
                digest.update(chunk)
            self.upload_digest = digest.hexdigest()
        finally:
            file.seek(position)
        return file

    def clean(self):
        data = super().clean()
        if not data.get("original_text") and not data.get("upload"):
            raise forms.ValidationError("Paste the original text or attach a document.")
        duplicate = bool(
            self.upload_digest
            and SourceDocument.objects.filter(
                owner=self.owner, sha256=self.upload_digest
            ).exists()
        )
        text = " ".join(data.get("original_text", "").split()).casefold()
        if text and not duplicate:
            existing_texts = (
                Notice.objects.filter(owner=self.owner)
                .exclude(original_text="")
                .values_list("original_text", flat=True)
                .iterator()
            )
            duplicate = any(
                " ".join(value.split()).casefold() == text for value in existing_texts
            )
        if duplicate and not data.get("confirm_duplicate"):
            self.add_error(
                "confirm_duplicate",
                "This file or text already exists in your notices. Confirm to save it again.",
            )
        return data


class NoticeEditForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = (
            "title",
            "summary",
            "category",
            "status",
            "target_program",
            "target_batch",
        )


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = (
            "title",
            "kind",
            "starts_at",
            "ends_at",
            "date_only",
            "source_timezone",
            "location",
            "duration_minutes",
            "notice",
            "opportunity",
            "completed",
        )
        widgets: ClassVar[dict] = {
            "starts_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "ends_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "date_only": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notice"].queryset = Notice.objects.filter(owner=owner)
        self.fields["opportunity"].queryset = Opportunity.objects.filter(owner=owner)
        for name in ("starts_at", "ends_at"):
            self.fields[name].input_formats = [
                "%Y-%m-%dT%H:%M",
                *self.fields[name].input_formats,
            ]
        self.fields[
            "starts_at"
        ].help_text = "Exact times use your profile timezone. Leave blank for date-only information."
        self.fields[
            "source_timezone"
        ].help_text = "Optional IANA timezone stated in the original source; does not change the time you enter."

    def clean_source_timezone(self):
        value = self.cleaned_data["source_timezone"]
        if value:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise forms.ValidationError(
                    "Enter a valid IANA timezone or leave blank."
                ) from exc
        return value


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = (
            "title",
            "description",
            "due_date",
            "priority",
            "notice",
            "opportunity",
        )
        widgets: ClassVar[dict] = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notice"].queryset = Notice.objects.filter(owner=owner)
        self.fields["opportunity"].queryset = Opportunity.objects.filter(owner=owner)


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = ("title", "category", "stage", "notes", "notice")

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notice"].queryset = Notice.objects.filter(owner=owner)
