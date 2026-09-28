from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from events.models import Event
from payments import paystack

from .models import Order, Ticket
from .serializers import CreateOrderSerializer, OrderSerializer
from .services import OrderError, create_order, mark_failed


def order_queryset(user):
    return (
        Order.objects.filter(buyer=user)
        .select_related("event")
        .prefetch_related(
            "items__ticket_type",
            Prefetch("tickets", queryset=Ticket.objects.select_related("ticket_type")),
        )
    )


class OrderListCreateView(ListAPIView):
    """GET: my orders (newest first). POST: reserve tickets and start payment."""

    serializer_class = OrderSerializer

    def get_queryset(self):
        return order_queryset(self.request.user)

    def post(self, request):
        data = CreateOrderSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        event = get_object_or_404(Event, slug=data.validated_data["event"])

        if not request.user.email:
            return Response({"detail": "Add an email address to your account first."}, status=400)

        try:
            order = create_order(buyer=request.user, event=event, items=data.validated_data["items"])
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        if order.status == Order.Status.PENDING:
            try:
                order.authorization_url = paystack.initialize_transaction(
                    email=order.email,
                    amount=order.total,
                    reference=order.reference,
                    callback_url=f"{settings.FRONTEND_URL}/payment/callback",
                    metadata={"event": event.slug, "order": order.reference},
                )
            except paystack.PaystackError as exc:
                mark_failed(order.reference, str(exc))
                return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
            order.save(update_fields=["authorization_url"])

        order = order_queryset(request.user).get(pk=order.pk)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(RetrieveAPIView):
    serializer_class = OrderSerializer
    lookup_field = "reference"

    def get_queryset(self):
        return order_queryset(self.request.user)
