from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Notice, SourceDocument


class CoreFeaturesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client.force_login(self.user)

    def test_notice_source_context_default_and_choices(self):
        notice = Notice.objects.create(
            owner=self.user,
            title="Important Announcement",
        )
        self.assertEqual(notice.source_context, Notice.SourceContext.OTHER)

        notice.source_context = Notice.SourceContext.PORTAL
        notice.save()
        self.assertEqual(notice.get_source_context_display(), "University portal")

    def test_capture_blank_or_omitted_source_context_is_filterable(self):
        for index, source in enumerate((None, "")):
            with self.subTest(source=source):
                data = {
                    "title": f"Notice {index}",
                    "original_text": f"Original {index}",
                    "category": "general",
                }
                if source is not None:
                    data["source_context"] = source
                response = self.client.post(reverse("capture"), data, secure=True)
                self.assertEqual(response.status_code, 302)
                notice = Notice.objects.get(title=data["title"])
                self.assertEqual(notice.source_context, Notice.SourceContext.OTHER)
                response = self.client.get(
                    reverse("inbox"), {"source_context": "other"}, secure=True
                )
                self.assertContains(response, notice.title)

    def test_edit_omitted_source_context_preserves_existing_value(self):
        notice = Notice.objects.create(
            owner=self.user, title="Notice", source_context=Notice.SourceContext.PORTAL
        )
        response = self.client.post(
            reverse("notice_edit", args=[notice.pk]),
            {"title": "Updated", "category": "general", "status": "review"},
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        notice.refresh_from_db()
        self.assertEqual(notice.source_context, Notice.SourceContext.PORTAL)

        response = self.client.post(
            reverse("notice_edit", args=[notice.pk]),
            {
                "title": "Updated",
                "category": "general",
                "status": "review",
                "source_context": "gmail",
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        notice.refresh_from_db()
        self.assertEqual(notice.source_context, Notice.SourceContext.GMAIL)

    def test_edit_blank_source_context_becomes_other(self):
        notice = Notice.objects.create(
            owner=self.user, title="Notice", source_context=Notice.SourceContext.PORTAL
        )
        response = self.client.post(
            reverse("notice_edit", args=[notice.pk]),
            {
                "title": "Notice",
                "category": "general",
                "status": "review",
                "source_context": "",
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        notice.refresh_from_db()
        self.assertEqual(notice.source_context, Notice.SourceContext.OTHER)

    def test_document_preview_non_image(self):
        doc = SourceDocument.objects.create(
            owner=self.user,
            original_name="document.pdf",
            file="document.pdf",
            sha256="dummy",
        )
        url = reverse("document_preview", args=[doc.pk])
        response = self.client.get(url, secure=True)
        self.assertEqual(response.status_code, 404)

