import hashlib
import hmac
import json

import pytest
import responses
from django.core import mail

from conftest import PAYSTACK_KEY
from orders.models import Order, Ticket

pytestmark = pytest.mark.django_db

INIT_URL = "https://api.paystack.co/transaction/initialize"


def verify_url(reference):
    return f"https://api.paystack.co/transaction/verify/{reference}"


def order_payload(event, *items):
    return {"event": event.slug, "items": [{"ticket_type": t.id, "quantity": q} for t, q in items]}


def signed_post(client, payload, key=PAYSTACK_KEY):
    body = json.dumps(payload).encode()
    signature = hmac.new(key.encode(), body, hashlib.sha512).hexdigest()
    return client.generic("POST", "/api/payments/webhook/", body, content_type="application/json",
                          HTTP_X_PAYSTACK_SIGNATURE=signature)


def charge_success(order, **overrides):
    data = {"reference": order.reference, "status": "success", "amount": order.total,
            "currency": "NGN", "channel": "card", "gateway_response": "Approved"}
    data.update(overrides)
    return {"event": "charge.success", "data": data}


class TestSimulator:
    def test_simulated_success(self, buy, buyer_api, event, regular, django_capture_on_commit_callbacks):
        reference = buy(event, (regular, 2)).data["reference"]
        with django_capture_on_commit_callbacks(execute=True):
            res = buyer_api.post("/api/payments/simulate/", {"reference": reference, "outcome": "success"})
        assert res.data["status"] == "paid"
        assert len(res.data["tickets"]) == 2
        assert len(mail.outbox) == 1

    def test_simulated_failure_releases_tickets(self, buy, buyer_api, event, regular):
        reference = buy(event, (regular, 2)).data["reference"]
        res = buyer_api.post("/api/payments/simulate/", {"reference": reference, "outcome": "failed"})
        assert res.data["status"] == "failed"
        regular.refresh_from_db()
        assert regular.reserved == 0

    def test_cannot_simulate_someone_elses_order(self, buy, other_api, event, regular):
        reference = buy(event, (regular, 1)).data["reference"]
        res = other_api.post("/api/payments/simulate/", {"reference": reference, "outcome": "success"})
        assert res.status_code == 404

    def test_disabled_when_paystack_is_configured(self, buyer_api, paystack_live):
        res = buyer_api.post("/api/payments/simulate/", {"reference": "GP-X", "outcome": "success"})
        assert res.status_code == 404


class TestPaystackCheckout:
    @responses.activate
    def test_initializes_transaction(self, buyer_api, paystack_live, event, regular):
        responses.post(INIT_URL, json={"status": True, "data": {
            "authorization_url": "https://checkout.paystack.com/abc123", "reference": "x"}})

        res = buyer_api.post("/api/orders/", order_payload(event, (regular, 2)), format="json")

        assert res.status_code == 201
        assert res.data["authorization_url"] == "https://checkout.paystack.com/abc123"
        sent = json.loads(responses.calls[0].request.body)
        assert sent["amount"] == 1_000_000
        assert sent["email"] == "tunde@example.com"
        assert sent["reference"] == res.data["reference"]
        assert sent["callback_url"].endswith("/payment/callback")
        assert responses.calls[0].request.headers["Authorization"] == f"Bearer {PAYSTACK_KEY}"

    @responses.activate
    def test_paystack_error_releases_tickets(self, buyer_api, paystack_live, event, regular):
        responses.post(INIT_URL, status=401, json={"status": False, "message": "Invalid key"})

        res = buyer_api.post("/api/orders/", order_payload(event, (regular, 2)), format="json")

        assert res.status_code == 502
        assert res.data["detail"] == "Invalid key"
        assert Order.objects.get().status == "failed"
        regular.refresh_from_db()
        assert regular.reserved == 0

    @responses.activate
    def test_verify_success_issues_tickets(self, buyer_api, paystack_live, event, regular):
        responses.post(INIT_URL, json={"status": True, "data": {"authorization_url": "https://p.co/x"}})
        order_ref = buyer_api.post("/api/orders/", order_payload(event, (regular, 1)), format="json").data["reference"]
        responses.get(verify_url(order_ref), json={"status": True, "data": {
            "status": "success", "amount": 500_000, "currency": "NGN", "channel": "bank_transfer",
            "gateway_response": "Successful"}})

        res = buyer_api.post("/api/payments/verify/", {"reference": order_ref})

        assert res.data["status"] == "paid"
        assert len(res.data["tickets"]) == 1
        assert Order.objects.get().payment_channel == "bank_transfer"

    @responses.activate
    @pytest.mark.parametrize("tx_status, expected", [("abandoned", "pending"), ("failed", "failed")])
    def test_verify_other_outcomes(self, buyer_api, paystack_live, event, regular, tx_status, expected):
        responses.post(INIT_URL, json={"status": True, "data": {"authorization_url": "https://p.co/x"}})
        order_ref = buyer_api.post("/api/orders/", order_payload(event, (regular, 1)), format="json").data["reference"]
        responses.get(verify_url(order_ref), json={"status": True, "data": {
            "status": tx_status, "amount": 500_000, "currency": "NGN"}})

        assert buyer_api.post("/api/payments/verify/", {"reference": order_ref}).data["status"] == expected

    @responses.activate
    def test_verify_rejects_underpayment(self, buyer_api, paystack_live, event, regular):
        responses.post(INIT_URL, json={"status": True, "data": {"authorization_url": "https://p.co/x"}})
        order_ref = buyer_api.post("/api/orders/", order_payload(event, (regular, 1)), format="json").data["reference"]
        responses.get(verify_url(order_ref), json={"status": True, "data": {
            "status": "success", "amount": 100, "currency": "NGN"}})

        assert buyer_api.post("/api/payments/verify/", {"reference": order_ref}).data["status"] == "pending"


class TestWebhook:
    @pytest.fixture
    def pending_order(self, buyer, event, regular, paystack_live):
        from orders.services import create_order
        return create_order(buyer=buyer, event=event, items=[{"ticket_type": regular.id, "quantity": 2}])

    def test_valid_webhook_issues_tickets(self, anon, pending_order):
        res = signed_post(anon, charge_success(pending_order))
        assert res.status_code == 200
        pending_order.refresh_from_db()
        assert pending_order.status == "paid"
        assert pending_order.tickets.count() == 2

    def test_bad_signature_is_rejected(self, anon, pending_order):
        res = signed_post(anon, charge_success(pending_order), key="sk_test_wrong")
        assert res.status_code == 401
        pending_order.refresh_from_db()
        assert pending_order.status == "pending"

    def test_missing_signature_is_rejected(self, anon, pending_order):
        res = anon.post("/api/payments/webhook/", charge_success(pending_order), format="json")
        assert res.status_code == 401

    def test_webhook_and_verify_together_issue_one_set_of_tickets(self, anon, pending_order):
        signed_post(anon, charge_success(pending_order))
        signed_post(anon, charge_success(pending_order))  # Paystack retries
        assert Ticket.objects.filter(order=pending_order).count() == 2

    def test_wrong_currency_is_ignored(self, anon, pending_order):
        signed_post(anon, charge_success(pending_order, currency="USD"))
        pending_order.refresh_from_db()
        assert pending_order.status == "pending"

    def test_unknown_reference_and_other_events_are_acknowledged(self, anon, pending_order):
        assert signed_post(anon, charge_success(pending_order, reference="GP-NOPE")).status_code == 200
        assert signed_post(anon, {"event": "transfer.success", "data": {}}).status_code == 200
