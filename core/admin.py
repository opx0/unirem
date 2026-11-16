from django.contrib import admin

from .models import (
    AuditEvent,
    Event,
    Notice,
    Opportunity,
    SourceDocument,
    StudentProfile,
    Task,
)


class PrivateAdmin(admin.ModelAdmin):
    readonly_fields = ("owner",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(owner=request.user)

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)

        class OwnerForm(form_class):
            def __init__(self, *args, **form_kwargs):
                super().__init__(*args, **form_kwargs)
                if not self.instance.pk:
                    self.instance.owner = request.user

        return OwnerForm

    def save_model(self, request, obj, form, change):
        if not change:
            obj.owner = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if (
            db_field.name in {"notice", "opportunity", "document"}
            and not request.user.is_superuser
        ):
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                owner=request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Notice)
class NoticeAdmin(PrivateAdmin):
    list_display = ("title", "owner", "category", "status", "created_at")
    list_filter = ("category", "status")
    search_fields = ("title", "original_text")


@admin.register(SourceDocument)
class SourceDocumentAdmin(PrivateAdmin):
    list_display = ("original_name", "owner", "uploaded_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Event)
class EventAdmin(PrivateAdmin):
    list_display = ("title", "owner", "kind", "starts_at", "date_only")


@admin.register(Task)
class TaskAdmin(PrivateAdmin):
    list_display = ("title", "owner", "due_date", "completed")


@admin.register(Opportunity)
class OpportunityAdmin(PrivateAdmin):
    list_display = ("title", "owner", "category", "stage")


@admin.register(AuditEvent)
class AuditAdmin(PrivateAdmin):
    list_display = ("notice", "owner", "action", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StudentProfile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "institution", "program", "batch", "timezone")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(user=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user" and not request.user.is_superuser:
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                pk=request.user.pk
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
