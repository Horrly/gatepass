import base64
import json

import pytest
import responses
from django.core.mail import EmailMultiAlternatives, get_connection

from config.email import BREVO_URL

pytestmark = pytest.mark.django_db


@pytest.fixture
def brevo(settings):
    settings.BREVO_API_KEY = "xkeysib-test"
    settings.DEFAULT_FROM_EMAIL = "Gatepass <tickets@example.com>"
    return get_connection("config.email.BrevoEmailBackend")


@responses.activate
def test_sends_html_email_with_attachments(brevo):
    responses.post(BREVO_URL, status=201, json={"messageId": "<abc@smtp-relay>"})
    message = EmailMultiAlternatives("Your tickets", "Plain body", to=["Tolu <tolu@example.com>"], connection=brevo)
    message.attach_alternative("<p>HTML body</p>", "text/html")
    message.attach("ticket-1.png", b"\x89PNG-bytes", "image/png")

    assert message.send() == 1

    request = responses.calls[0].request
    assert request.headers["api-key"] == "xkeysib-test"
    body = json.loads(request.body)
    assert body["sender"] == {"email": "tickets@example.com", "name": "Gatepass"}
    assert body["to"] == [{"email": "tolu@example.com", "name": "Tolu"}]
    assert body["subject"] == "Your tickets"
    assert body["textContent"] == "Plain body"
    assert body["htmlContent"] == "<p>HTML body</p>"
    assert body["attachment"] == [{"name": "ticket-1.png", "content": base64.b64encode(b"\x89PNG-bytes").decode()}]


@responses.activate
def test_api_errors_raise_so_celery_retries(brevo):
    responses.post(BREVO_URL, status=401, json={"message": "Key not found"})
    message = EmailMultiAlternatives("Hi", "Body", to=["a@example.com"], connection=brevo)
    with pytest.raises(RuntimeError, match="Brevo error 401"):
        message.send()


@responses.activate
def test_fail_silently(settings):
    settings.BREVO_API_KEY = "xkeysib-test"
    responses.post(BREVO_URL, status=500, body="boom")
    connection = get_connection("config.email.BrevoEmailBackend", fail_silently=True)
    assert EmailMultiAlternatives("Hi", "Body", to=["a@example.com"], connection=connection).send() == 0
