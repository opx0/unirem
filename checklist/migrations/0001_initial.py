from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChecklistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("completed", models.BooleanField(default=False)),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checklist_items", to="core.task")),
            ],
            options={"ordering": ("pk",)},
        ),
    ]
