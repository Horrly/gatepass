from django.conf import settings
from rest_framework import serializers

from .models import Order, OrderItem, Ticket


class OrderEventSerializer(serializers.Serializer):
    slug = serializers.CharField()
    title = serializers.CharField()
    venue = serializers.CharField()
    city = serializers.CharField()
    starts_at = serializers.DateTimeField()


class OrderItemSerializer(serializers.ModelSerializer):
    ticket_type = serializers.CharField(source="ticket_type.name")

    class Meta:
        model = OrderItem
        fields = ["ticket_type", "quantity", "unit_price"]


class TicketSerializer(serializers.ModelSerializer):
    ticket_type = serializers.CharField(source="ticket_type.name")

    class Meta:
        model = Ticket
        fields = ["code", "ticket_type", "checked_in_at"]


class OrderSerializer(serializers.ModelSerializer):
    event = OrderEventSerializer()
    items = OrderItemSerializer(many=True)
    tickets = TicketSerializer(many=True)
    authorization_url = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "reference", "status", "total", "email", "event", "items", "tickets",
            "created_at", "paid_at", "expires_at", "authorization_url",
        ]

    def get_authorization_url(self, order):
        return order.authorization_url if order.status == Order.Status.PENDING else None


class OrderItemInputSerializer(serializers.Serializer):
    ticket_type = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0, max_value=settings.MAX_TICKETS_PER_ORDER)


class CreateOrderSerializer(serializers.Serializer):
    event = serializers.SlugField()
    items = OrderItemInputSerializer(many=True, allow_empty=False)
