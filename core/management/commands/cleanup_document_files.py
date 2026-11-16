from django.core.management.base import BaseCommand, CommandError

from core.models import PendingFileDeletion, SourceDocument


class Command(BaseCommand):
    help = "Retry deletion of queued source document files."

    def handle(self, *args, **options):
        storage = SourceDocument._meta.get_field("file").storage
        failures = 0
        for pending in PendingFileDeletion.objects.all().iterator():
            try:
                storage.delete(pending.name)
            except Exception as exc:  # noqa: BLE001 - retain failures from any storage backend
                failures += 1
                self.stderr.write(f"Failed to delete {pending.name}: {exc}")
                continue
            pending.delete()
        if failures:
            raise CommandError(
                f"{failures} file deletion(s) failed; retry this command."
            )
