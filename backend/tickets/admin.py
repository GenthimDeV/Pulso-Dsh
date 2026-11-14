from django.contrib import admin

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
    autocomplete_fields = ["requester", "assignee", "category"]
    date_hierarchy = "created_at"
    # El estado solo cambia a través de la máquina de estados (tickets/services.py, 2.2).
    readonly_fields = ["code", "status", "resolved_at", "sla_due_at", "updated_at"]
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


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "is_internal", "created_at"]
    list_filter = ["is_internal"]
    search_fields = ["ticket__code", "body", "author__username"]
    list_select_related = ["ticket", "author"]
    autocomplete_fields = ["ticket", "author"]


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
