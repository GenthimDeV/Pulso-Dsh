from django.db.models import Case, IntegerField, Prefetch, Q, Value, When
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAgent, IsRequester, user_role

from . import metrics, services
from .models import Category, Comment, Ticket, TicketEvent
from .serializers import (
    AssignInputSerializer,
    CategorySerializer,
    CommentInputSerializer,
    CommentSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
    TransitionInputSerializer,
)
from .services import InvalidTransition, TransitionError, create_ticket

# Código de error del servicio -> HTTP (los no listados, p. ej. assignee_required, son 400).
SERVICE_ERROR_STATUS = {
    "invalid_transition": status.HTTP_409_CONFLICT,
    "not_an_agent": status.HTTP_403_FORBIDDEN,
    "invalid_assignee": status.HTTP_400_BAD_REQUEST,
}

# Orden por gravedad (no alfabético): urgent < high < medium < low.
PRIORITY_BY_SEVERITY = [
    Ticket.Priority.URGENT,
    Ticket.Priority.HIGH,
    Ticket.Priority.MEDIUM,
    Ticket.Priority.LOW,
]
PRIORITY_RANK = Case(
    *[When(priority=code, then=Value(rank)) for rank, code in enumerate(PRIORITY_BY_SEVERITY)],
    output_field=IntegerField(),
)
# Campos por los que se puede ordenar (`?ordering=campo` o `?ordering=-campo`).
ORDERING_FIELDS = {"created_at", "updated_at", "sla_due_at", "priority"}
# Un id con más dígitos que esto no cabe en un entero de BD: se rechaza con 400 en vez de dar 500.
MAX_ID_DIGITS = 9


class TicketPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TicketViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Lista, detalle y creación de tickets.

    Permisos: clase de permiso (agente o solicitante) + `get_queryset` por rol, de modo que
    un solicitante recibe 404 ante el código de un ticket ajeno.
    """

    permission_classes = [IsAgent | IsRequester]
    pagination_class = TicketPagination
    lookup_field = "code"

    def _visible(self):
        queryset = Ticket.objects.select_related("category", "requester", "assignee")
        if user_role(self.request.user) != "agent":
            queryset = queryset.filter(requester=self.request.user)
        return queryset

    @staticmethod
    def _with_detail(queryset):
        return queryset.prefetch_related(
            Prefetch("comments", Comment.objects.select_related("author")),
            Prefetch("events", TicketEvent.objects.select_related("actor")),
        )

    def get_queryset(self):
        queryset = self._visible()

        if self.action == "retrieve":
            return self._with_detail(queryset)
        if self.action == "list":
            queryset = self._filter(queryset)
            return self._order(queryset)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        if self.action == "retrieve":
            return TicketDetailSerializer
        return TicketListSerializer

    def _filter(self, queryset):
        params = self.request.query_params

        value = params.get("status")
        if value:
            if value not in Ticket.Status.values:
                raise ValidationError({"status": "invalid_choice"})
            queryset = queryset.filter(status=value)

        value = params.get("priority")
        if value:
            if value not in Ticket.Priority.values:
                raise ValidationError({"priority": "invalid_choice"})
            queryset = queryset.filter(priority=value)

        # `assignee`: id de agente, `me` (los míos) o `none` (sin asignar).
        value = params.get("assignee")
        if value:
            if value == "none":
                queryset = queryset.filter(assignee__isnull=True)
            elif value == "me":
                queryset = queryset.filter(assignee=self.request.user)
            elif value.isascii() and value.isdigit() and len(value) <= MAX_ID_DIGITS:
                queryset = queryset.filter(assignee_id=int(value))
            else:
                raise ValidationError({"assignee": "invalid"})

        # Postgres rechaza el NUL en un literal (500); SQLite no, y solo fallaba en producción.
        term = params.get("search", "").replace("\x00", "").strip()
        if term:
            queryset = queryset.filter(
                Q(subject__icontains=term)
                | Q(code__icontains=term)
                | Q(requester__username__icontains=term)
                | Q(requester__first_name__icontains=term)
                | Q(requester__last_name__icontains=term)
            )
        return queryset

    def _order(self, queryset):
        ordering = self.request.query_params.get("ordering", "-created_at")
        descending = ordering.startswith("-")
        field = ordering.removeprefix("-")
        if field not in ORDERING_FIELDS:
            raise ValidationError({"ordering": "invalid_choice"})

        if field == "priority":
            queryset = queryset.annotate(priority_rank=PRIORITY_RANK)
            field = "priority_rank"
        # `pk` desempata para que la paginación sea estable.
        return queryset.order_by(f"-{field}" if descending else field, "-pk")

    def _detail_response(self, ticket, status_code=status.HTTP_200_OK):
        # Se relee con el queryset de detalle para devolver la misma forma que GET.
        ticket = self._with_detail(self._visible()).get(pk=ticket.pk)
        data = TicketDetailSerializer(ticket, context=self.get_serializer_context()).data
        return Response(data, status=status_code)

    def create(self, request, *args, **kwargs):
        data = self._validated(TicketCreateSerializer, request.data)
        ticket = create_ticket(requester=request.user, **data)
        return self._detail_response(ticket, status.HTTP_201_CREATED)

    @staticmethod
    def _service_error(error):
        """Traduce un error del servicio a respuesta: solo códigos, nunca textos."""
        body = {"code": error.code}
        if isinstance(error, InvalidTransition):
            body.update({"from": error.from_status, "to": error.to_status})
        return Response(body, status=SERVICE_ERROR_STATUS.get(error.code, 400))

    @staticmethod
    def _validated(serializer_class, data):
        """Valida la entrada de una acción; los fallos salen como `{campo: código}`, sin textos."""
        serializer = serializer_class(data=data)
        if not serializer.is_valid():
            raise ValidationError(
                {field: errors[0].code for field, errors in serializer.errors.items()}
            )
        return serializer.validated_data

    @action(detail=True, methods=["post"], permission_classes=[IsAgent])
    def transition(self, request, code=None):
        ticket = self.get_object()
        data = self._validated(TransitionInputSerializer, request.data)
        try:
            services.transition(ticket, data["to"], request.user, assignee=data.get("assignee"))
        except TransitionError as error:
            if isinstance(error, InvalidTransition):
                services.record_rejection(ticket, error, request.user)
            return self._service_error(error)
        return self._detail_response(ticket)

    @action(detail=True, methods=["post"], permission_classes=[IsAgent])
    def assign(self, request, code=None):
        ticket = self.get_object()
        data = self._validated(AssignInputSerializer, request.data)
        try:
            services.assign(ticket, data["assignee"], request.user)
        except TransitionError as error:
            return self._service_error(error)
        return self._detail_response(ticket)

    @action(detail=True, methods=["post"])
    def comments(self, request, code=None):
        # `get_object` ya da 404 al solicitante ante un ticket ajeno.
        ticket = self.get_object()
        data = self._validated(CommentInputSerializer, request.data)
        try:
            comment = services.add_comment(ticket, request.user, **data)
        except TransitionError as error:
            return self._service_error(error)
        data = CommentSerializer(comment, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)


class MetricsSummaryView(APIView):
    """`GET /metrics/summary/?range=today|7d|30d` (solo agentes)."""

    permission_classes = [IsAgent]

    def get(self, request):
        range_code = request.query_params.get("range") or metrics.DEFAULT_RANGE
        if range_code not in metrics.RANGES:
            raise ValidationError({"range": "invalid_choice"})
        return Response(metrics.summary(range_code))


class AgentListView(APIView):
    """`GET /agents/`: agentes con su carga frente a la capacidad (solo agentes)."""

    permission_classes = [IsAgent]

    def get(self, request):
        return Response(metrics.agent_loads())


class CategoryListView(APIView):
    """`GET /categories/`: categorías para el formulario de nuevo ticket."""

    permission_classes = [IsAgent | IsRequester]

    def get(self, request):
        return Response(CategorySerializer(Category.objects.all(), many=True).data)
