from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.permissions import user_role

from .models import Category, Comment, Ticket, TicketEvent
from .services import allowed_transitions

User = get_user_model()


class UserRefSerializer(serializers.ModelSerializer):
    """Referencia mínima a un usuario (solicitante, asignado, autor, actor)."""

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class TicketListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    requester = UserRefSerializer(read_only=True)
    assignee = UserRefSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "code",
            "subject",
            "priority",
            "status",
            "category",
            "requester",
            "assignee",
            "created_at",
            "updated_at",
            "resolved_at",
            "sla_due_at",
        ]


class CommentSerializer(serializers.ModelSerializer):
    author = UserRefSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "body", "is_internal", "created_at"]


class TicketEventSerializer(serializers.ModelSerializer):
    actor = UserRefSerializer(read_only=True)

    class Meta:
        model = TicketEvent
        fields = ["id", "type", "actor", "from_status", "to_status", "created_at"]


class TicketDetailSerializer(TicketListSerializer):
    """Detalle con conversación e historial. Un solicitante nunca recibe notas internas."""

    comments = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    allowed_transitions = serializers.SerializerMethodField()

    class Meta(TicketListSerializer.Meta):
        fields = [
            *TicketListSerializer.Meta.fields,
            "description",
            "comments",
            "events",
            "allowed_transitions",
        ]

    def _is_agent(self):
        return user_role(self.context["request"].user) == "agent"

    # Usan `.all()` sobre el prefetch de la vista; el filtro se aplica en Python
    # (son pocas filas por ticket) para no romper el prefetch con un `.filter()`.
    def get_comments(self, ticket):
        comments = ticket.comments.all()
        if not self._is_agent():
            comments = [c for c in comments if not c.is_internal]
        return CommentSerializer(comments, many=True, context=self.context).data

    def get_events(self, ticket):
        events = ticket.events.all()
        if not self._is_agent():
            events = [e for e in events if e.type != TicketEvent.Type.INTERNAL_NOTE]
        return TicketEventSerializer(events, many=True, context=self.context).data

    def get_allowed_transitions(self, ticket):
        # Solo los agentes cambian estados: para un solicitante no hay acciones.
        if not self._is_agent():
            return []
        return sorted(allowed_transitions(ticket.status))


class TransitionInputSerializer(serializers.Serializer):
    """Entrada de POST /tickets/{code}/transition/. `assignee` solo vale al pasar a `assigned`."""

    to = serializers.ChoiceField(choices=Ticket.Status.choices)
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )


class AssignInputSerializer(serializers.Serializer):
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class CommentInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)
    is_internal = serializers.BooleanField(default=False)


class TicketCreateSerializer(serializers.ModelSerializer):
    """Entrada de POST /tickets/. `requester`, `status` y el SLA los fija el servidor."""

    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    subject = serializers.CharField(max_length=200)

    class Meta:
        model = Ticket
        fields = ["subject", "description", "category", "priority"]
