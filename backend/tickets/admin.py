from django.contrib import admin
from django.db import transaction

from .models import Category, Comment, Ticket, TicketEvent


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


class CommentInline(admin.StackedInline):
    model = Comment
    extra = 0
    fields = ["author", "body", "is_internal", "created_at"]
    autocomplete_fields = ["author"]


def _record_comment_event(comment, actor):
    """Deja en el historial el comentario creado desde el admin."""
    TicketEvent.objects.create(
        ticket=comment.ticket,
        actor=actor,
        type=TicketEvent.Type.INTERNAL_NOTE if comment.is_internal else TicketEvent.Type.COMMENTED,
    )


class TicketEventInline(admin.TabularInline):
    """Historial de solo lectura: lo escribe la capa de servicios, no el admin."""

    model = TicketEvent
    extra = 0
    can_delete = False
    fields = ["created_at", "type", "actor", "from_status", "to_status"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "subject",
        "status",
        "priority",
        "category",
        "requester",
        "assignee",
        "created_at",
        "sla_due_at",
    ]
    list_filter = ["status", "priority", "category", "assignee"]
    search_fields = ["code", "subject", "requester__username", "requester__email"]
    list_select_related = ["category", "requester", "assignee"]
    autocomplete_fields = ["requester", "category"]
    date_hierarchy = "created_at"
    # Estado y asignado solo cambian a través de la máquina de estados (tickets/services.py, 2.2).
    readonly_fields = ["code", "status", "assignee", "resolved_at", "sla_due_at", "updated_at"]
    fields = [
        "code",
        "subject",
        "description",
        ("priority", "category"),
        ("requester", "assignee"),
        ("status", "resolved_at"),
        ("created_at", "sla_due_at", "updated_at"),
    ]
    inlines = [CommentInline, TicketEventInline]

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if not change:
                TicketEvent.objects.create(
                    ticket=obj, actor=request.user, type=TicketEvent.Type.CREATED
                )

    def save_formset(self, request, form, formset, change):
        if formset.model is not Comment:
            return super().save_formset(request, form, formset, change)
        with transaction.atomic():
            comments = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for comment in comments:
                is_new = comment.pk is None
                comment.save()
                if is_new:
                    _record_comment_event(comment, request.user)
            formset.save_m2m()


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "is_internal", "created_at"]
    list_filter = ["is_internal"]
    search_fields = ["ticket__code", "body", "author__username"]
    list_select_related = ["ticket", "author"]
    autocomplete_fields = ["ticket", "author"]

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if not change:
                _record_comment_event(obj, request.user)


@admin.register(TicketEvent)
class TicketEventAdmin(admin.ModelAdmin):
    list_display = ["ticket", "type", "actor", "from_status", "to_status", "created_at"]
    list_filter = ["type"]
    search_fields = ["ticket__code", "actor__username"]
    list_select_related = ["ticket", "actor"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
