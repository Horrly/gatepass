import uuid

from django.db.models import Count, F, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from orders.models import Order, OrderItem, Ticket
from orders.services import CheckInResult, check_in

from .models import Event, TicketType
from .permissions import IsOrganizerOrReadOnly
from .serializers import EventSerializer, OrganizerTicketTypeSerializer


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    lookup_field = "slug"
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOrganizerOrReadOnly]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = Event.objects.select_related("organizer").prefetch_related("ticket_types")
        user = self.request.user

        if self.action == "list":
            qs = qs.published().upcoming()
            if q := self.request.query_params.get("q", "").strip():
                qs = qs.filter(Q(title__icontains=q) | Q(venue__icontains=q) | Q(city__icontains=q))
            if city := self.request.query_params.get("city", "").strip():
                qs = qs.filter(city__iexact=city)
            return qs

        # Detail views: anyone sees published events; organizers also see their drafts.
        if user.is_authenticated:
            return qs.filter(Q(is_published=True) | Q(organizer=user))
        return qs.published()

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user, is_published=False)

    def perform_destroy(self, event):
        if event.orders.exists():
            raise PermissionDenied("Events with orders can't be deleted. Unpublish it instead.")
        event.delete()

    def _organizer_event(self, slug):
        event = get_object_or_404(Event, slug=slug)
        if event.organizer_id != self.request.user.id:
            raise PermissionDenied("Only the organizer can do that.")
        return event

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def mine(self, request):
        events = (
            Event.objects.filter(organizer=request.user)
            .prefetch_related("ticket_types")
            .order_by("-starts_at")
        )
        return Response(EventSerializer(events, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="ticket-types",
            permission_classes=[permissions.IsAuthenticated])
    def add_ticket_type(self, request, slug=None):
        event = self._organizer_event(slug)
        serializer = OrganizerTicketTypeSerializer(data=request.data, context={"event": event})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def stats(self, request, slug=None):
        event = self._organizer_event(slug)
        paid_items = OrderItem.objects.filter(order__event=event, order__status=Order.Status.PAID)

        by_type = []
        for ticket_type in event.ticket_types.all():
            items = paid_items.filter(ticket_type=ticket_type)
            sold = items.aggregate(n=Sum("quantity"))["n"] or 0
            revenue = items.aggregate(r=Sum(F("quantity") * F("unit_price")))["r"] or 0
            by_type.append({
                "id": ticket_type.id,
                "name": ticket_type.name,
                "price": ticket_type.price,
                "quantity": ticket_type.quantity,
                "sold": sold,
                "on_hold": max(ticket_type.reserved - sold, 0),
                "revenue": revenue,
            })

        tickets = Ticket.objects.filter(order__event=event, order__status=Order.Status.PAID)
        recent = (
            event.orders.filter(status=Order.Status.PAID)
            .select_related("buyer")
            .annotate(ticket_count=Count("tickets"))
            .order_by("-paid_at")[:10]
        )
        return Response({
            "tickets_sold": tickets.count(),
            "checked_in": tickets.filter(checked_in_at__isnull=False).count(),
            "revenue": sum(t["revenue"] for t in by_type),
            "orders": event.orders.filter(status=Order.Status.PAID).count(),
            "by_ticket_type": by_type,
            "recent_orders": [
                {
                    "reference": o.reference,
                    "buyer": o.buyer.username,
                    "tickets": o.ticket_count,
                    "total": o.total,
                    "paid_at": o.paid_at,
                }
                for o in recent
            ],
        })

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def checkin(self, request, slug=None):
        event = self._organizer_event(slug)
        raw = str(request.data.get("code", "")).strip()
        try:
            code = uuid.UUID(raw)
        except ValueError:
            return Response({"result": CheckInResult.INVALID, "detail": "That isn't a Gatepass ticket code."})

        result, ticket = check_in(event=event, code=code, staff=request.user)
        messages = {
            CheckInResult.OK: "Valid ticket — admitted.",
            CheckInResult.ALREADY: "This ticket has already been used.",
            CheckInResult.INVALID: "Ticket not found or not paid for.",
            CheckInResult.WRONG_EVENT: "This ticket is for a different event.",
        }
        body = {"result": result, "detail": messages[result]}
        if ticket and result != CheckInResult.WRONG_EVENT:
            body["ticket"] = {
                "code": str(ticket.code),
                "ticket_type": ticket.ticket_type.name,
                "holder": ticket.order.buyer.username,
                "order": ticket.order.reference,
                "checked_in_at": ticket.checked_in_at,
            }
        return Response(body)


class TicketTypeViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """PATCH / DELETE /api/ticket-types/<id>/ — organizer only."""

    serializer_class = OrganizerTicketTypeSerializer
    http_method_names = ["patch", "delete"]

    def get_queryset(self):
        return TicketType.objects.filter(event__organizer=self.request.user)

    def perform_destroy(self, ticket_type):
        if ticket_type.order_items.exists():
            raise PermissionDenied("This ticket type has orders. Set its quantity to what's sold instead.")
        ticket_type.delete()
