from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from events.views import EventViewSet, TicketTypeViewSet
from orders.views import OrderDetailView, OrderListCreateView
from payments.views import SimulatePaymentView, VerifyPaymentView, paystack_webhook

from .views import health, spa

router = DefaultRouter()
router.register("events", EventViewSet, basename="event")
router.register("ticket-types", TicketTypeViewSet, basename="ticket-type")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/orders/", OrderListCreateView.as_view(), name="orders"),
    path("api/orders/<str:reference>/", OrderDetailView.as_view(), name="order-detail"),
    path("api/payments/verify/", VerifyPaymentView.as_view(), name="payment-verify"),
    path("api/payments/simulate/", SimulatePaymentView.as_view(), name="payment-simulate"),
    path("api/payments/webhook/", paystack_webhook, name="paystack-webhook"),
    path("api/", include(router.urls)),
    # Everything else is a React route.
    re_path(r"^(?!api/|admin/|static/).*$", spa, name="spa"),
]
