from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0005_pendingfiledeletion")]

    operations = [
        migrations.AddField(
            model_name="notice",
            name="is_read",
            field=models.BooleanField(default=False),
        ),
    ]
