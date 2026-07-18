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

from rest_framework import viewsets
from rest_framework.decorators import action
from .models import OrganizationSponsor, Bounty, BountyClaim
from .serializers import OrganizationSponsorSerializer, BountySerializer, BountyClaimSerializer
from .services import payout_bounty

class OrganizationSponsorViewSet(viewsets.ModelViewSet):
    queryset = OrganizationSponsor.objects.all()
    serializer_class = OrganizationSponsorSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class BountyViewSet(viewsets.ModelViewSet):
    queryset = Bounty.objects.all()
    serializer_class = BountySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def claim(self, request, pk=None):
        bounty = self.get_object()
        if not bounty.is_active:
            return Response({"error": "Bounty is no longer active."}, status=400)
            
        claim, created = BountyClaim.objects.get_or_create(
            bounty=bounty,
            user=request.user
        )
        if not created:
            return Response({"status": "already_claimed", "claim_id": claim.id})
            
        return Response({"status": "claimed", "claim_id": claim.id})

class BountyClaimViewSet(viewsets.ModelViewSet):
    queryset = BountyClaim.objects.all()
    serializer_class = BountyClaimSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Users see their own claims. Admins could see all.
        return self.queryset.filter(user=self.request.user)
        
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def approve_payout(self, request, pk=None):
        claim = self.get_object()
        if claim.is_approved:
            return Response({"error": "Already approved."}, status=400)
            
        claim = payout_bounty(claim.user, claim.bounty)
        
        return Response({
            "status": "payout_processed",
            "payout_id": claim.payout_id
        })
