from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CheckoutSessionView,
    SubscriptionStatusView,
    CancelSubscriptionView,
    StripePortalView,
    PlanListView,
    InvoiceViewSet,
    OrganizationSponsorViewSet,
    BountyViewSet,
    BountyClaimViewSet,
)
from .webhooks import stripe_webhook

router = DefaultRouter()
router.register(r"sponsors", OrganizationSponsorViewSet)
router.register(r"bounties", BountyViewSet)
router.register(r"bounty-claims", BountyClaimViewSet)
router.register(r"invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("checkout/", CheckoutSessionView.as_view(), name="checkout"),
    path("portal/", StripePortalView.as_view(), name="portal"),
    path("status/", SubscriptionStatusView.as_view(), name="status"),
    path("cancel/", CancelSubscriptionView.as_view(), name="cancel"),
    path("plans/", PlanListView.as_view(), name="plans"),
    path("webhook/", stripe_webhook, name="stripe-webhook"),
    path("stripe-webhook/", stripe_webhook, name="stripe-webhook-alt"),
    path("", include(router.urls)),
]
