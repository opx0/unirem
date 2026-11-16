from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reminders", "0003_reminder_task_reminder_task_due_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="reminder",
            name="relative_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
