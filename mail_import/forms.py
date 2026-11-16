from pathlib import Path

from django import forms

from .services import MAX_FILE_SIZE, MailError, parse_mail


class MailImportForm(forms.Form):
    file = forms.FileField(label="Email file (.eml)")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if Path(upload.name).suffix.lower() != ".eml":
            raise forms.ValidationError("Choose an .eml file.")
        if upload.content_type not in (
            "message/rfc822",
            "application/octet-stream",
            "application/vnd.ms-outlook",
            "text/plain",
            "",
        ):
            raise forms.ValidationError("Unsupported upload content type.")
        if upload.size > MAX_FILE_SIZE:
            raise forms.ValidationError("The email exceeds 5 MB.")
        raw = upload.read(MAX_FILE_SIZE + 1)
        try:
            self.parsed_mail = parse_mail(raw)
        except MailError as exc:
            raise forms.ValidationError(str(exc)) from exc
        self.raw_mail = raw
        return upload
