from rest_framework import views, permissions
from rest_framework.response import Response
from .models import SubscriptionPlan, CustomerSubscription
import stripe
from django.conf import settings

stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', 'sk_test_mock')

class CheckoutSessionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id')
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Plan not found"}, status=404)
        
        # Mocking for now
        checkout_url = "https://checkout.stripe.com/mock-session-id"
        
        return Response({"checkout_url": checkout_url})

class SubscriptionStatusView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            sub = request.user.subscription
            return Response({
                "active": sub.active,
                "plan": sub.plan.name if sub.plan else None,
                "current_period_end": sub.current_period_end
            })
        except CustomerSubscription.DoesNotExist:
            return Response({"active": False, "plan": None})
