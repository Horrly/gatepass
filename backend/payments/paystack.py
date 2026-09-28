"""Minimal Paystack client: https://paystack.com/docs/api/transaction/

Flow: we *initialize* a transaction and send the buyer to Paystack's hosted
checkout. Paystack then tells us the result twice — by redirecting the buyer
back (we *verify* the reference server-side) and by calling our *webhook*.
We never trust the browser alone: both paths re-check with Paystack.
"""

import hashlib
import hmac
from urllib.parse import urlencode

import requests
from django.conf import settings


class PaystackError(Exception):
    pass


def _headers():
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _request(method, path, **kwargs):
    try:
        res = requests.request(
            method, f"{settings.PAYSTACK_BASE_URL}{path}", headers=_headers(), timeout=15, **kwargs
        )
        body = res.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaystackError("Couldn't reach Paystack. Please try again.") from exc
    if not res.ok or not body.get("status"):
        raise PaystackError(body.get("message") or f"Paystack error ({res.status_code})")
    return body["data"]


def initialize_transaction(*, email, amount, reference, callback_url, metadata=None):
    """Returns the URL of Paystack's checkout page for this payment."""
    if settings.PAYMENT_SIMULATOR:
        return f"{settings.FRONTEND_URL}/payment/simulate?{urlencode({'reference': reference})}"
    data = _request(
        "POST",
        "/transaction/initialize",
        json={
            "email": email,
            "amount": amount,
            "reference": reference,
            "currency": "NGN",
            "callback_url": callback_url,
            "metadata": metadata or {},
        },
    )
    return data["authorization_url"]


def verify_transaction(reference):
    """Returns Paystack's transaction data: status, amount, currency, channel, ..."""
    return _request("GET", f"/transaction/verify/{reference}")


def valid_signature(raw_body, signature):
    """Webhooks are signed with HMAC-SHA512 of the raw body, keyed with our secret key."""
    if not settings.PAYSTACK_SECRET_KEY or not signature:
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
