"""Create an idempotent synthetic demonstration for an existing student account."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Event, Notice, Opportunity, Task


class Command(BaseCommand):
    help = "Seed synthetic campus notices for an existing username (no real data)."

    def add_arguments(self, parser):
        parser.add_argument("username")

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError("Create the student account first.")
        notice, _ = Notice.objects.get_or_create(
            owner=user,
            title="Demo: two KYC meetings",
            defaults={
                "category": "placement",
                "original_text": "Example University: Group A KYC 10:00–10:30; Group B KYC 11:00–11:30 on 3 February 2027. Bring ID.",
                "summary": "Two separate meetings. Bring ID.",
            },
        )
        zone = ZoneInfo("Asia/Kolkata")
        for title, hour in (("Group A KYC", 10), ("Group B KYC", 11)):
            Event.objects.get_or_create(
                owner=user,
                notice=notice,
                title=f"Demo: {title}",
                defaults={
                    "kind": Event.Kind.ATTEND,
                    "starts_at": datetime(2027, 2, 3, hour, tzinfo=zone),
                    "ends_at": datetime(2027, 2, 3, hour, 30, tzinfo=zone),
                    "source_timezone": "Asia/Kolkata",
                },
            )
        Task.objects.get_or_create(owner=user, notice=notice, title="Demo: bring ID")
        assessment, _ = Notice.objects.get_or_create(
            owner=user,
            title="Demo: shortlisted assessment",
            defaults={
                "category": "placement",
                "original_text": "Example University: shortlisted candidates may take the online assessment on 8 February 2027. Duration 45 minutes. Bring a charged laptop and photo ID. Reporting instructions will follow.",
            },
        )
        Opportunity.objects.get_or_create(
            owner=user,
            notice=assessment,
            title="Demo: Example Company",
            defaults={"stage": Opportunity.Stage.SHORTLISTED},
        )
        Event.objects.get_or_create(
            owner=user,
            notice=assessment,
            title="Demo: assessment date (time unknown)",
            defaults={"kind": Event.Kind.WINDOW, "date_only": date(2027, 2, 8)},
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Synthetic demo records are ready; no notifications were scheduled."
            )
        )
