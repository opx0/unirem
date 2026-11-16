import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]  # noqa: RUF012

    operations = [  # noqa: RUF012
        migrations.CreateModel(
            name="SourceConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("manual", "Manual")], max_length=20)),
                ("connected_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("owner", "source"), name="unique_owner_source_connection"),
                    models.CheckConstraint(condition=models.Q(("source", "manual")), name="connection_manual_only"),
                ],
            },
        ),
    ]
