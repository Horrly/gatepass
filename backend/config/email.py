"""Django email backend that sends through Brevo's HTTP API.

Many free hosts (including Render's free plan) block outgoing SMTP ports, so
emails are sent over HTTPS instead: https://developers.brevo.com/reference/sendtransacemail
"""

import base64
import logging
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _address(value):
    name, email = parseaddr(value)
    return {"email": email, "name": name} if name else {"email": email}


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
                sent += 1
            except Exception:
                logger.exception("Brevo couldn't send email to %s", message.to)
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        payload = {
            "sender": _address(message.from_email or settings.DEFAULT_FROM_EMAIL),
            "to": [_address(addr) for addr in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }
        html = next((content for content, mime in getattr(message, "alternatives", []) if mime == "text/html"), None)
        if html:
            payload["htmlContent"] = html
        if message.cc:
            payload["cc"] = [_address(addr) for addr in message.cc]
        if message.bcc:
            payload["bcc"] = [_address(addr) for addr in message.bcc]

        attachments = []
        for attachment in message.attachments:
            filename, content, _mimetype = attachment  # (name, bytes, mimetype) tuples
            if isinstance(content, str):
                content = content.encode()
            attachments.append({"name": filename, "content": base64.b64encode(content).decode()})
        if attachments:
            payload["attachment"] = attachments

        res = requests.post(
            BREVO_URL,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
            timeout=20,
        )
        if res.status_code >= 400:
            raise RuntimeError(f"Brevo error {res.status_code}: {res.text[:300]}")
