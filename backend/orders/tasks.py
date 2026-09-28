import io
import logging

import qrcode
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Order
from .services import release_expired_holds

logger = logging.getLogger(__name__)


def qr_png(data):
    buffer = io.BytesIO()
    qrcode.make(data, box_size=8, border=2).save(buffer, format="PNG")
    return buffer.getvalue()


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_tickets_email(order_id):
    order = (
        Order.objects.select_related("event", "buyer")
        .prefetch_related("tickets__ticket_type")
        .get(id=order_id)
    )
    tickets = list(order.tickets.all())
    context = {
        "order": order,
        "event": order.event,
        "starts_at": timezone.localtime(order.event.starts_at),
        "tickets": tickets,
        "tickets_url": f"{settings.FRONTEND_URL}/tickets",
        "total_naira": order.total / 100,
    }

    message = EmailMultiAlternatives(
        subject=f"Your tickets for {order.event.title}",
        body=render_to_string("emails/tickets.txt", context),
        to=[order.email],
    )
    message.attach_alternative(render_to_string("emails/tickets.html", context), "text/html")
    for index, ticket in enumerate(tickets, start=1):
        message.attach(f"ticket-{index}-{ticket.ticket_type.name}.png", qr_png(str(ticket.code)), "image/png")
    message.send()
    logger.info("Sent %s ticket(s) for order %s to %s", len(tickets), order.reference, order.email)


@shared_task
def release_expired_holds_task():
    released = release_expired_holds()
    if released:
        logger.info("Released %s expired order hold(s).", released)
    return released
