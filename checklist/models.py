from django.db import models


class ChecklistItem(models.Model):
    task = models.ForeignKey(
        "core.Task", on_delete=models.CASCADE, related_name="checklist_items"
    )
    title = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ("pk",)

    def __str__(self):
        return self.title
