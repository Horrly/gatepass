"""Create a demo organizer with sample events and some sales. Safe to run on every deploy.

    python manage.py seed_demo

- Resets the demo password so the README credentials always work.
- Creates the sample events once, then keeps them in the future on later runs
  (so the live demo never shows an empty "no upcoming events" page).
"""

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from events.models import Event, TicketType
from orders.models import Order, OrderItem, Ticket

NAIRA = 100  # kobo

EVENTS = [
    {
        "slug": "lagos-tech-meetup",
        "title": "Lagos Tech Meetup",
        "venue": "Landmark Centre, Victoria Island",
        "city": "Lagos",
        "days_ahead": 12,
        "hour": 10,
        "description": "A day of talks and demos from engineers building products across Africa — "
        "payments, logistics, AI and developer tools. Networking lunch included.",
        "tickets": [("Regular", 5_000, 200, "Access to all talks"), ("VIP", 15_000, 40, "Front seats, lunch with speakers")],
        "sales": [("Regular", 3), ("Regular", 2), ("VIP", 1), ("Regular", 1)],
    },
    {
        "slug": "ife-hackathon",
        "title": "Ife Campus Hackathon",
        "venue": "Obafemi Awolowo University, Ile-Ife",
        "city": "Ile-Ife",
        "days_ahead": 25,
        "hour": 9,
        "description": "24 hours, teams of four, one problem statement revealed on the day. "
        "Mentors, food and prizes for the top three teams.",
        "tickets": [("Student", 0, 150, "Free with a valid student ID"), ("Professional", 2_000, 50, "")],
        "sales": [("Student", 2), ("Student", 1), ("Professional", 1)],
    },
    {
        "slug": "afrobeats-night-ibadan",
        "title": "Afrobeats Night Ibadan",
        "venue": "Cultural Centre, Mokola",
        "city": "Ibadan",
        "days_ahead": 40,
        "hour": 19,
        "description": "Live bands, DJs and the best of Afrobeats until late.",
        "tickets": [("Early bird", 3_000, 100, ""), ("Regular", 5_000, 300, ""), ("Table for 4", 60_000, 10, "")],
        "sales": [("Early bird", 2), ("Early bird", 4), ("Regular", 2), ("Table for 4", 1)],
    },
]


class Command(BaseCommand):
    help = "Create the demo organizer, sample events and sales (idempotent)."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("DEMO_USERNAME", "demo")
        password = os.environ.get("DEMO_PASSWORD", "Demo-pass-123")

        demo, created = User.objects.get_or_create(username=username, defaults={"email": "demo@example.com"})
        demo.set_password(password)
        demo.save()
        self.stdout.write(f"{'Created' if created else 'Updated'} demo user '{username}'.")

        now = timezone.now()
        for spec in EVENTS:
            # Local (Lagos) wall-clock time, so a 7pm show really says 7pm.
            starts_at = timezone.localtime(now + timedelta(days=spec["days_ahead"])).replace(
                hour=spec["hour"], minute=0, second=0, microsecond=0
            )
            event = Event.objects.filter(slug=spec["slug"]).first()
            if event:
                if event.starts_at < now:  # keep the demo fresh
                    event.starts_at, event.ends_at = starts_at, starts_at + timedelta(hours=8)
                    event.save(update_fields=["starts_at", "ends_at"])
                    self.stdout.write(f"Moved '{event.title}' back into the future.")
                continue
            self._create_event(spec, demo, starts_at)
            self.stdout.write(f"Created event '{spec['title']}'.")

    @transaction.atomic
    def _create_event(self, spec, organizer, starts_at):
        event = Event.objects.create(
            organizer=organizer,
            slug=spec["slug"],
            title=spec["title"],
            description=spec["description"],
            venue=spec["venue"],
            city=spec["city"],
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=8),
            is_published=True,
        )
        types = {
            name: TicketType.objects.create(
                event=event, name=name, price=price * NAIRA, quantity=qty, description=desc
            )
            for name, price, qty, desc in spec["tickets"]
        }

        # Sample sales so the organizer dashboard has something to show.
        # Created directly (no emails) for made-up buyers.
        User = get_user_model()
        for i, (type_name, qty) in enumerate(spec["sales"], start=1):
            buyer, _ = User.objects.get_or_create(
                username=f"guest{i}", defaults={"email": f"guest{i}@example.com"}
            )
            ticket_type = types[type_name]
            order = Order.objects.create(
                event=event, buyer=buyer, email=buyer.email, total=ticket_type.price * qty,
                status=Order.Status.PAID, paid_at=timezone.now(), payment_channel="card",
            )
            OrderItem.objects.create(order=order, ticket_type=ticket_type, quantity=qty, unit_price=ticket_type.price)
            Ticket.objects.bulk_create(Ticket(order=order, ticket_type=ticket_type) for _ in range(qty))
            TicketType.objects.filter(id=ticket_type.id).update(reserved=F("reserved") + qty)
