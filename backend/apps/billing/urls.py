from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CheckoutSessionView, SubscriptionStatusView, OrganizationSponsorViewSet, BountyViewSet, BountyClaimViewSet
from .webhooks import stripe_webhook

router = DefaultRouter()
router.register(r'sponsors', OrganizationSponsorViewSet)
router.register(r'bounties', BountyViewSet)
router.register(r'bounty-claims', BountyClaimViewSet)

urlpatterns = [
    path('checkout/', CheckoutSessionView.as_view(), name='checkout'),
    path('status/', SubscriptionStatusView.as_view(), name='status'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
    path('', include(router.urls)),
]
