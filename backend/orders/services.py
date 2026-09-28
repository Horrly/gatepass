"""Order lifecycle: reserve -> pay -> issue tickets (or expire and release).

All inventory changes happen inside transactions with row locks
(`select_for_update`), so two buyers racing for the last ticket can't both get it.
"""

import logging
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from events.models import TicketType

from .models import Order, OrderItem, Ticket

logger = logging.getLogger(__name__)


class OrderError(Exception):
    """A problem the buyer can fix (sold out, too many tickets, ...)."""


def release_expired_holds(event=None):
    """Expire unpaid orders past their hold time and give their tickets back. Returns the count."""
    stale = Order.objects.filter(status=Order.Status.PENDING, expires_at__lt=timezone.now())
    if event is not None:
        stale = stale.filter(event=event)

    released = 0
    for order_id in stale.values_list("id", flat=True):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            if order.status != Order.Status.PENDING:
                continue  # paid or failed in the meantime
            _release_inventory(order)
            order.status = Order.Status.EXPIRED
            order.save(update_fields=["status"])
            released += 1
    return released


def _release_inventory(order):
    for item in order.items.all():
        TicketType.objects.filter(id=item.ticket_type_id).update(reserved=F("reserved") - item.quantity)


def create_order(*, buyer, event, items):
    """Reserve tickets and create a pending order.

    `items` is a list of {"ticket_type": id, "quantity": n}. Free orders are
    fulfilled immediately; paid ones wait for Paystack.
    """
    if not event.is_published or event.has_ended:
        raise OrderError("Tickets for this event aren't on sale.")

    quantities = Counter()
    for item in items:
        if item["quantity"] > 0:
            quantities[item["ticket_type"]] += item["quantity"]
    if not quantities:
        raise OrderError("Choose at least one ticket.")
    if sum(quantities.values()) > settings.MAX_TICKETS_PER_ORDER:
        raise OrderError(f"You can buy at most {settings.MAX_TICKETS_PER_ORDER} tickets per order.")

    # Free up tickets from abandoned checkouts before checking availability.
    release_expired_holds(event)

    with transaction.atomic():
        # Lock in a consistent order (by id) to avoid deadlocks between concurrent buyers.
        ticket_types = {
            t.id: t
            for t in TicketType.objects.select_for_update().filter(event=event, id__in=quantities).order_by("id")
        }
        if len(ticket_types) != len(quantities):
            raise OrderError("One of the selected tickets doesn't belong to this event.")

        for type_id, qty in quantities.items():
            ticket_type = ticket_types[type_id]
            if qty > ticket_type.available:
                if ticket_type.available == 0:
                    raise OrderError(f"{ticket_type.name} is sold out.")
                raise OrderError(f"Only {ticket_type.available} {ticket_type.name} ticket(s) left.")

        total = sum(ticket_types[t].price * q for t, q in quantities.items())
        order = Order.objects.create(
            event=event,
            buyer=buyer,
            email=buyer.email,
            total=total,
            expires_at=timezone.now() + timedelta(minutes=settings.ORDER_HOLD_MINUTES),
        )
        for type_id, qty in quantities.items():
            ticket_type = ticket_types[type_id]
            OrderItem.objects.create(order=order, ticket_type=ticket_type, quantity=qty, unit_price=ticket_type.price)
            TicketType.objects.filter(id=type_id).update(reserved=F("reserved") + qty)

    if total == 0:
        fulfill_order(order.reference)
        order.refresh_from_db()
    return order


def fulfill_order(reference, *, amount=None, channel="", gateway_response=""):
    """Mark an order paid and issue its tickets. Safe to call more than once.

    Called from both the buyer's verify request and Paystack's webhook — whichever
    arrives first does the work; the other is a no-op. Returns True if this call
    issued the tickets.
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(reference=reference)

        if order.status == Order.Status.PAID:
            return False
        if amount is not None and amount != order.total:
            logger.error("Amount mismatch for %s: paid %s, expected %s", reference, amount, order.total)
            return False

        if order.status in (Order.Status.EXPIRED, Order.Status.FAILED):
            # The buyer paid after their hold ran out. Their money is real, so honour
            # the order and take the tickets back — this can briefly exceed capacity.
            logger.warning("Late payment for %s (was %s); re-reserving tickets.", reference, order.status)
            for item in order.items.all():
                TicketType.objects.filter(id=item.ticket_type_id).update(reserved=F("reserved") + item.quantity)

        order.status = Order.Status.PAID
        order.paid_at = timezone.now()
        order.payment_channel = channel or ("free" if order.total == 0 else "")
        order.gateway_response = gateway_response[:200]
        order.save()

        Ticket.objects.bulk_create(
            Ticket(order=order, ticket_type_id=item.ticket_type_id)
            for item in order.items.all()
            for _ in range(item.quantity)
        )

    from .tasks import send_tickets_email

    transaction.on_commit(lambda: send_tickets_email.delay(order.id))
    return True


def mark_failed(reference, gateway_response=""):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(reference=reference)
        if order.status != Order.Status.PENDING:
            return False
        _release_inventory(order)
        order.status = Order.Status.FAILED
        order.gateway_response = gateway_response[:200]
        order.save(update_fields=["status", "gateway_response"])
        return True


class CheckInResult:
    OK = "ok"
    ALREADY = "already_checked_in"
    INVALID = "invalid"
    WRONG_EVENT = "wrong_event"


def check_in(*, event, code, staff):
    """Admit a ticket at the door. Returns (result, ticket_or_None)."""
    with transaction.atomic():
        ticket = (
            Ticket.objects.select_for_update()
            .select_related("order", "ticket_type", "order__buyer")
            .filter(code=code, order__status=Order.Status.PAID)
            .first()
        )
        if ticket is None:
            return CheckInResult.INVALID, None
        if ticket.order.event_id != event.id:
            return CheckInResult.WRONG_EVENT, ticket
        if ticket.checked_in_at:
            return CheckInResult.ALREADY, ticket

        ticket.checked_in_at = timezone.now()
        ticket.checked_in_by = staff
        ticket.save(update_fields=["checked_in_at", "checked_in_by"])
        return CheckInResult.OK, ticket
