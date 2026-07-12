from django.urls import path
from .views import CheckoutSessionView, SubscriptionStatusView
from .webhooks import stripe_webhook

urlpatterns = [
    path('checkout/', CheckoutSessionView.as_view(), name='checkout'),
    path('status/', SubscriptionStatusView.as_view(), name='status'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
]
