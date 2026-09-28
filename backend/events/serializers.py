from django.utils import timezone
from rest_framework import serializers

from .models import Event, TicketType

MIN_PAID_PRICE = 100_00  # ₦100, in kobo


class TicketTypeSerializer(serializers.ModelSerializer):
    available = serializers.IntegerField(read_only=True)

    class Meta:
        model = TicketType
        fields = ["id", "name", "description", "price", "quantity", "available"]

    def validate_price(self, value):
        if 0 < value < MIN_PAID_PRICE:
            raise serializers.ValidationError("Paid tickets must cost at least ₦100 (10000 kobo).")
        return value

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        if self.instance and value < self.instance.reserved:
            raise serializers.ValidationError(
                f"{self.instance.reserved} tickets are already sold or on hold."
            )
        return value

    def validate(self, attrs):
        # Changing the price after people have bought would make orders inconsistent.
        if self.instance and self.instance.reserved and "price" in attrs:
            if attrs["price"] != self.instance.price:
                raise serializers.ValidationError(
                    {"price": "You can't change the price after tickets have been sold."}
                )
        return attrs

    def create(self, validated_data):
        event = self.context["event"]
        if event.ticket_types.filter(name__iexact=validated_data["name"]).exists():
            raise serializers.ValidationError({"name": "This event already has a ticket with that name."})
        return TicketType.objects.create(event=event, **validated_data)


class OrganizerTicketTypeSerializer(TicketTypeSerializer):
    class Meta(TicketTypeSerializer.Meta):
        fields = TicketTypeSerializer.Meta.fields + ["reserved"]


class EventSerializer(serializers.ModelSerializer):
    organizer = serializers.CharField(source="organizer.username", read_only=True)
    ticket_types = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    is_sold_out = serializers.SerializerMethodField()
    is_organizer = serializers.SerializerMethodField()
    has_ended = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id", "slug", "title", "description", "venue", "city", "starts_at", "ends_at",
            "is_published", "has_ended", "organizer", "is_organizer", "ticket_types",
            "min_price", "is_sold_out",
        ]
        read_only_fields = ["slug"]

    def _is_organizer(self, event):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and event.organizer_id == request.user.id)

    def get_is_organizer(self, event):
        return self._is_organizer(event)

    def get_ticket_types(self, event):
        serializer = OrganizerTicketTypeSerializer if self._is_organizer(event) else TicketTypeSerializer
        return serializer(event.ticket_types.all(), many=True).data

    def get_min_price(self, event):
        prices = [t.price for t in event.ticket_types.all()]
        return min(prices) if prices else None

    def get_is_sold_out(self, event):
        types = event.ticket_types.all()
        return bool(types) and all(t.available == 0 for t in types)

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if "starts_at" in attrs and attrs["starts_at"] < timezone.now():
            raise serializers.ValidationError({"starts_at": "The event must start in the future."})
        if ends_at and starts_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "The end time must be after the start time."})

        if attrs.get("is_published"):
            if not self.instance or not self.instance.ticket_types.exists():
                raise serializers.ValidationError(
                    {"is_published": "Add at least one ticket type before publishing."}
                )
        return attrs
