import uuid

from django.conf import settings
from django.db import models
from django.utils.crypto import get_random_string

from events.models import Event, TicketType


def new_reference():
    return f"GP-{get_random_string(12, allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789')}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        PAID = "paid", "Paid"
        FAILED = "failed", "Payment failed"
        EXPIRED = "expired", "Expired"

    reference = models.CharField(max_length=32, unique=True, default=new_reference)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="orders")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    email = models.EmailField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    total = models.PositiveIntegerField(help_text="In kobo.")
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Paystack checkout page for this order (reused if the buyer retries).
    authorization_url = models.URLField(max_length=300, blank=True)
    # Filled from Paystack once the payment is confirmed.
    payment_channel = models.CharField(max_length=30, blank=True)
    gateway_response = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    ticket_type = models.ForeignKey(TicketType, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveIntegerField(help_text="Price at the time of purchase, in kobo.")

    @property
    def subtotal(self):
        return self.quantity * self.unit_price


class Ticket(models.Model):
    """One admission. `code` is what the QR code encodes and what gets scanned at the door."""

    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tickets")
    ticket_type = models.ForeignKey(TicketType, on_delete=models.PROTECT, related_name="tickets")
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return str(self.code)
