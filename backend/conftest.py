from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from config.celery import app as celery_app
from events.models import Event, TicketType

User = get_user_model()
PASSWORD = "Str0ng-pass-123"
PAYSTACK_KEY = "sk_test_dummy_key_for_tests"


@pytest.fixture(autouse=True)
def eager_celery():
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True


@pytest.fixture
def simulator(settings):
    settings.PAYSTACK_SECRET_KEY = ""
    settings.PAYMENT_SIMULATOR = True
    return settings


@pytest.fixture
def paystack_live(settings):
    settings.PAYSTACK_SECRET_KEY = PAYSTACK_KEY
    settings.PAYMENT_SIMULATOR = False
    return settings


@pytest.fixture
def organizer(db):
    return User.objects.create_user(username="ada", email="ada@example.com", password=PASSWORD)


@pytest.fixture
def buyer(db):
    return User.objects.create_user(username="tunde", email="tunde@example.com", password=PASSWORD)


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="chioma", email="chioma@example.com", password=PASSWORD)


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


@pytest.fixture
def anon():
    return client_for()


@pytest.fixture
def org_api(organizer):
    return client_for(organizer)


@pytest.fixture
def buyer_api(buyer):
    return client_for(buyer)


@pytest.fixture
def other_api(other_user):
    return client_for(other_user)


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        organizer=organizer,
        title="Lagos Tech Meetup",
        venue="Landmark Centre",
        city="Lagos",
        starts_at=timezone.now() + timedelta(days=10),
        is_published=True,
    )


@pytest.fixture
def regular(event):
    return TicketType.objects.create(event=event, name="Regular", price=500_000, quantity=5)


@pytest.fixture
def vip(event):
    return TicketType.objects.create(event=event, name="VIP", price=1_500_000, quantity=2)


@pytest.fixture
def free(event):
    return TicketType.objects.create(event=event, name="Student", price=0, quantity=10)


@pytest.fixture
def buy(buyer_api, simulator):
    """Place an order through the API (simulator mode). Returns the response."""

    def _buy(event, *items, client=None):
        payload = {
            "event": event.slug,
            "items": [{"ticket_type": t.id, "quantity": q} for t, q in items],
        }
        return (client or buyer_api).post("/api/orders/", payload, format="json")

    return _buy
