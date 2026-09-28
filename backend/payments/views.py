import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from orders.serializers import OrderSerializer
from orders.services import fulfill_order, mark_failed
from orders.views import order_queryset

from . import paystack

logger = logging.getLogger(__name__)


def apply_paystack_result(order, data):
    """Update an order from Paystack transaction data (from verify or a webhook)."""
    tx_status = data.get("status")
    if tx_status == "success":
        if data.get("currency", "NGN") != "NGN":
            logger.error("Unexpected currency %s for %s", data.get("currency"), order.reference)
            return
        fulfill_order(
            order.reference,
            amount=int(data.get("amount", -1)),
            channel=data.get("channel") or "",
            gateway_response=data.get("gateway_response") or "",
        )
    elif tx_status in ("failed", "reversed"):
        mark_failed(order.reference, data.get("gateway_response") or tx_status)
    # "abandoned", "ongoing", "pending": the buyer may still pay — leave it pending.


class ReferenceSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=32)


class VerifyPaymentView(APIView):
    """Called by the payment callback page after Paystack redirects the buyer back."""

    def post(self, request):
        data = ReferenceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = get_object_or_404(order_queryset(request.user), reference=data.validated_data["reference"])

        if order.status == Order.Status.PENDING and not settings.PAYMENT_SIMULATOR:
            try:
                apply_paystack_result(order, paystack.verify_transaction(order.reference))
            except paystack.PaystackError as exc:
                logger.warning("Verify failed for %s: %s", order.reference, exc)

        order = order_queryset(request.user).get(pk=order.pk)
        return Response(OrderSerializer(order).data)


class SimulatePaymentView(APIView):
    """Stand-in for Paystack's checkout when no secret key is configured (local dev and demos)."""

    class Input(ReferenceSerializer):
        outcome = serializers.ChoiceField(choices=["success", "failed"])

    def post(self, request):
        if not settings.PAYMENT_SIMULATOR:
            return Response({"detail": "Payment simulator is disabled."}, status=status.HTTP_404_NOT_FOUND)
        data = self.Input(data=request.data)
        data.is_valid(raise_exception=True)
        order = get_object_or_404(order_queryset(request.user), reference=data.validated_data["reference"])

        if data.validated_data["outcome"] == "success":
            apply_paystack_result(
                order,
                {"status": "success", "amount": order.total, "currency": "NGN",
                 "channel": "simulated", "gateway_response": "Simulated payment"},
            )
        else:
            apply_paystack_result(order, {"status": "failed", "gateway_response": "Simulated decline"})

        order = order_queryset(request.user).get(pk=order.pk)
        return Response(OrderSerializer(order).data)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """Paystack calls this for every transaction event. Must be fast and idempotent."""
    if not paystack.valid_signature(request.body, request.headers.get("x-paystack-signature")):
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)

    if payload.get("event") == "charge.success":
        data = payload.get("data") or {}
        order = Order.objects.filter(reference=data.get("reference")).first()
        if order:
            apply_paystack_result(order, data)
        else:
            logger.warning("Webhook for unknown reference %s", data.get("reference"))

    # Always 200 for authentic requests, or Paystack keeps retrying.
    return HttpResponse(status=200)
