"""Many buyers racing for the last tickets at the same moment.

SQLite serialises all writes and ignores SELECT ... FOR UPDATE, so this test only
means something on PostgreSQL (which CI uses). It's skipped on SQLite.
"""

import threading
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.utils import timezone

from events.models import Event, TicketType
from orders.models import Order
from orders.services import OrderError, create_order

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="needs PostgreSQL row locking"),
]

BUYERS = 12
CAPACITY = 5


def test_concurrent_buyers_cannot_oversell():
    User = get_user_model()
    organizer = User.objects.create_user(username="org", email="org@example.com")
    event = Event.objects.create(organizer=organizer, title="Hot Event", venue="x", city="Lagos",
                                 starts_at=timezone.now() + timedelta(days=3), is_published=True)
    ticket_type = TicketType.objects.create(event=event, name="GA", price=100_000, quantity=CAPACITY)
    buyers = [User.objects.create_user(username=f"b{i}", email=f"b{i}@example.com") for i in range(BUYERS)]

    start = threading.Barrier(BUYERS)
    results = []

    def attempt(user):
        try:
            start.wait()  # everyone fires at once
            create_order(buyer=user, event=event, items=[{"ticket_type": ticket_type.id, "quantity": 1}])
            results.append("ok")
        except OrderError:
            results.append("sold_out")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt, args=(u,)) for u in buyers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ticket_type.refresh_from_db()
    assert results.count("ok") == CAPACITY
    assert results.count("sold_out") == BUYERS - CAPACITY
    assert ticket_type.reserved == CAPACITY
    assert Order.objects.count() == CAPACITY
