from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from orders.models import Order, Ticket
from orders.services import fulfill_order, mark_failed, release_expired_holds

pytestmark = pytest.mark.django_db


def refresh(*objs):
    for obj in objs:
        obj.refresh_from_db()


class TestCreateOrder:
    def test_reserves_tickets_and_returns_checkout_url(self, buy, event, regular, vip):
        res = buy(event, (regular, 2), (vip, 1))
        assert res.status_code == 201
        assert res.data["status"] == "pending"
        assert res.data["total"] == 2 * 500_000 + 1_500_000
        assert "/payment/simulate?reference=GP-" in res.data["authorization_url"]
        assert res.data["tickets"] == []  # no tickets until paid

        refresh(regular, vip)
        assert (regular.reserved, vip.reserved) == (2, 1)

    def test_prevents_overselling(self, buy, event, vip, other_api):
        assert buy(event, (vip, 2)).status_code == 201
        res = buy(event, (vip, 1), client=other_api)
        assert res.status_code == 409
        assert res.data["detail"] == "VIP is sold out."

    def test_reports_how_many_are_left(self, buy, event, regular):
        res = buy(event, (regular, 6))
        assert res.status_code == 409
        assert res.data["detail"] == "Only 5 Regular ticket(s) left."

    def test_max_tickets_per_order(self, buy, event, regular, free):
        res = buy(event, (regular, 5), (free, 6))
        assert res.status_code == 409
        assert "at most 10" in res.data["detail"]

    def test_rejects_empty_selection(self, buy, event, regular):
        assert buy(event, (regular, 0)).status_code == 409

    def test_rejects_ticket_type_from_another_event(self, buy, event, organizer, regular):
        from events.models import Event, TicketType
        other = Event.objects.create(organizer=organizer, title="Other", venue="x", city="y",
                                     starts_at=event.starts_at, is_published=True)
        foreign = TicketType.objects.create(event=other, name="GA", price=0, quantity=5)
        res = buy(event, (foreign, 1))
        assert res.status_code == 409

    def test_rejects_unpublished_and_past_events(self, buy, event, regular):
        event.is_published = False
        event.save()
        assert buy(event, (regular, 1)).status_code == 409

        event.is_published = True
        event.starts_at = timezone.now() - timedelta(days=1)
        event.save()
        assert buy(event, (regular, 1)).status_code == 409

    def test_requires_login(self, anon, event, regular, simulator):
        res = anon.post("/api/orders/", {"event": event.slug, "items": [{"ticket_type": regular.id, "quantity": 1}]},
                        format="json")
        assert res.status_code == 401

    def test_free_order_is_issued_immediately_and_emailed(self, buy, event, free, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            res = buy(event, (free, 2))
        assert res.data["status"] == "paid"
        assert res.data["authorization_url"] is None
        assert len(res.data["tickets"]) == 2

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == ["tunde@example.com"]
        assert "Lagos Tech Meetup" in email.subject
        assert len(email.attachments) == 2  # one QR code per ticket
        assert email.attachments[0][2] == "image/png"


class TestHoldsAndFulfilment:
    def test_expired_holds_release_inventory(self, buy, event, vip, other_api):
        reference = buy(event, (vip, 2)).data["reference"]
        Order.objects.filter(reference=reference).update(expires_at=timezone.now() - timedelta(minutes=1))

        # The next buyer's attempt releases the stale hold first, so it succeeds.
        assert buy(event, (vip, 1), client=other_api).status_code == 201
        assert Order.objects.get(reference=reference).status == "expired"
        vip.refresh_from_db()
        assert vip.reserved == 1

    def test_release_task_skips_unexpired_orders(self, buy, event, regular):
        buy(event, (regular, 1))
        assert release_expired_holds() == 0

    def test_fulfil_is_idempotent(self, buy, event, regular, django_capture_on_commit_callbacks):
        reference = buy(event, (regular, 2)).data["reference"]
        with django_capture_on_commit_callbacks(execute=True):
            assert fulfill_order(reference, amount=1_000_000) is True
            assert fulfill_order(reference, amount=1_000_000) is False

        assert Ticket.objects.filter(order__reference=reference).count() == 2
        assert len(mail.outbox) == 1
        regular.refresh_from_db()
        assert regular.reserved == 2

    def test_amount_mismatch_is_not_fulfilled(self, buy, event, regular):
        reference = buy(event, (regular, 1)).data["reference"]
        assert fulfill_order(reference, amount=100) is False
        assert Order.objects.get(reference=reference).status == "pending"

    def test_late_payment_is_honoured(self, buy, event, regular):
        reference = buy(event, (regular, 2)).data["reference"]
        Order.objects.filter(reference=reference).update(expires_at=timezone.now() - timedelta(minutes=1))
        release_expired_holds()
        regular.refresh_from_db()
        assert regular.reserved == 0

        assert fulfill_order(reference, amount=1_000_000) is True
        regular.refresh_from_db()
        assert regular.reserved == 2
        assert Order.objects.get(reference=reference).status == "paid"

    def test_failed_payment_releases_inventory(self, buy, event, regular):
        reference = buy(event, (regular, 3)).data["reference"]
        assert mark_failed(reference, "Declined") is True
        assert mark_failed(reference, "Declined") is False
        regular.refresh_from_db()
        assert regular.reserved == 0


class TestMyOrders:
    def test_lists_only_my_orders(self, buy, event, regular, buyer_api, other_api):
        reference = buy(event, (regular, 1)).data["reference"]
        assert [o["reference"] for o in buyer_api.get("/api/orders/").data] == [reference]
        assert other_api.get("/api/orders/").data == []
        assert other_api.get(f"/api/orders/{reference}/").status_code == 404
        assert buyer_api.get(f"/api/orders/{reference}/").status_code == 200
