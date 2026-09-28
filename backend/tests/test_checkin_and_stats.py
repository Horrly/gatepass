from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from events.models import Event
from orders.models import Order
from orders.services import fulfill_order

pytestmark = pytest.mark.django_db


@pytest.fixture
def paid_order(buy, event, regular, vip):
    reference = buy(event, (regular, 2), (vip, 1)).data["reference"]
    fulfill_order(reference, amount=2_500_000, channel="card")
    return Order.objects.get(reference=reference)


def scan(client, event, code):
    return client.post(f"/api/events/{event.slug}/checkin/", {"code": str(code)}, format="json")


class TestCheckIn:
    def test_admits_a_valid_ticket_once(self, org_api, event, paid_order):
        ticket = paid_order.tickets.first()

        first = scan(org_api, event, ticket.code)
        assert first.data["result"] == "ok"
        assert first.data["ticket"]["holder"] == "tunde"

        again = scan(org_api, event, ticket.code)
        assert again.data["result"] == "already_checked_in"
        assert again.data["ticket"]["checked_in_at"] is not None

    def test_rejects_unpaid_and_garbage_codes(self, org_api, buy, event, regular):
        reference = buy(event, (regular, 1)).data["reference"]
        order = Order.objects.get(reference=reference)
        # Pending orders have no tickets; make sure random UUIDs and junk are rejected.
        assert order.tickets.count() == 0
        assert scan(org_api, event, "3f2b8c1e-0000-4000-8000-000000000000").data["result"] == "invalid"
        assert scan(org_api, event, "not-a-code").data["result"] == "invalid"

    def test_rejects_ticket_for_another_event(self, org_api, organizer, paid_order):
        other = Event.objects.create(organizer=organizer, title="Other", venue="x", city="y",
                                     starts_at=timezone.now() + timedelta(days=2), is_published=True)
        res = scan(org_api, other, paid_order.tickets.first().code)
        assert res.data["result"] == "wrong_event"
        assert "ticket" not in res.data

    def test_only_organizer_can_scan(self, other_api, buyer_api, event, paid_order):
        code = paid_order.tickets.first().code
        assert scan(other_api, event, code).status_code == 403
        assert scan(buyer_api, event, code).status_code == 403


class TestStats:
    def test_dashboard_numbers(self, org_api, buy, event, regular, vip, paid_order):
        buy(event, (regular, 1))  # pending: counts as on hold, not sold
        scan(org_api, event, paid_order.tickets.first().code)

        stats = org_api.get(f"/api/events/{event.slug}/stats/").data

        assert stats["tickets_sold"] == 3
        assert stats["checked_in"] == 1
        assert stats["orders"] == 1
        assert stats["revenue"] == 2_500_000
        regular_row = next(r for r in stats["by_ticket_type"] if r["name"] == "Regular")
        assert (regular_row["sold"], regular_row["on_hold"], regular_row["revenue"]) == (2, 1, 1_000_000)
        assert stats["recent_orders"][0]["reference"] == paid_order.reference

    def test_stats_are_private(self, other_api, event):
        assert other_api.get(f"/api/events/{event.slug}/stats/").status_code == 403


class TestSeedDemo:
    def test_creates_demo_data_and_is_idempotent(self, django_user_model):
        call_command("seed_demo")
        call_command("seed_demo")

        demo = django_user_model.objects.get(username="demo")
        assert demo.check_password("Demo-pass-123")
        assert Event.objects.filter(organizer=demo, is_published=True).count() == 3
        assert Order.objects.filter(status="paid").count() == 11

        hackathon = Event.objects.get(slug="ife-hackathon")
        student = hackathon.ticket_types.get(name="Student")
        assert student.reserved == 3  # matches the seeded sales

    def test_moves_past_demo_events_forward(self):
        call_command("seed_demo")
        Event.objects.filter(slug="lagos-tech-meetup").update(starts_at=timezone.now() - timedelta(days=2))
        call_command("seed_demo")
        assert Event.objects.get(slug="lagos-tech-meetup").starts_at > timezone.now()


class TestDeployment:
    def test_health_check(self, anon):
        assert anon.get("/api/health/").json() == {"status": "ok"}

    def test_spa_fallback(self, client, settings, tmp_path):
        (tmp_path / "index.html").write_text("<div id='root'></div>")
        settings.FRONTEND_DIST = tmp_path
        res = client.get("/events/lagos-tech-meetup")
        assert res.status_code == 200
        assert client.get("/api/nope/").status_code == 404
