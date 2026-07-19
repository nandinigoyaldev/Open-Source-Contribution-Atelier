from rest_framework import views, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse, FileResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import stripe
from .models import SubscriptionPlan, CustomerSubscription, Invoice
from .serializers import (
    SubscriptionPlanSerializer,
    CustomerSubscriptionSerializer,
    InvoiceSerializer,
)

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock")


class PlanListView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        plans = SubscriptionPlan.objects.all()
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data)


class CheckoutSessionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get("plan_id")
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Plan not found"}, status=404)

        # Check if in mock / testing mode
        is_mock = (
            getattr(settings, "TESTING", False)
            or stripe.api_key == "sk_test_mock"
            or not stripe.api_key
        )

        if is_mock:
            # Instantly update subscription status locally for seamless local development
            sub, _ = CustomerSubscription.objects.get_or_create(
                user=request.user,
                defaults={"stripe_customer_id": f"cus_mock_{request.user.id}"},
            )
            if not sub.stripe_customer_id:
                sub.stripe_customer_id = f"cus_mock_{request.user.id}"
            sub.stripe_subscription_id = f"sub_mock_{request.user.id}"
            sub.plan = plan
            sub.active = True
            sub.status = "active"
            sub.current_period_end = timezone.now() + timedelta(days=30)
            sub.payment_failed_at = None
            sub.save()

            checkout_url = settings.FRONTEND_URL + "/settings/billing?success=true"
            return Response({"checkout_url": checkout_url})

        try:
            sub, _ = CustomerSubscription.objects.get_or_create(
                user=request.user, defaults={"stripe_customer_id": ""}
            )

            if not sub.stripe_customer_id:
                stripe_customer = stripe.Customer.create(
                    email=request.user.email, metadata={"user_id": request.user.id}
                )
                sub.stripe_customer_id = stripe_customer.id
                sub.save()

            # If user already has a subscription active on Stripe, they should use Customer Portal
            # but if they want to subscribe to a new plan, create a checkout session
            session = stripe.checkout.Session.create(
                customer=sub.stripe_customer_id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": plan.stripe_price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url=settings.FRONTEND_URL + "/settings/billing?success=true",
                cancel_url=settings.FRONTEND_URL + "/settings/billing?canceled=true",
                metadata={"user_id": request.user.id, "plan_id": plan.id},
            )
            return Response({"checkout_url": session.url})
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class StripePortalView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        is_mock = (
            getattr(settings, "TESTING", False)
            or stripe.api_key == "sk_test_mock"
            or not stripe.api_key
        )

        if is_mock:
            return Response({"url": settings.FRONTEND_URL + "/settings/billing"})

        try:
            sub = request.user.subscription
            if not sub.stripe_customer_id:
                return Response(
                    {"error": "No billing profile found. Please subscribe first."},
                    status=400,
                )

            session = stripe.billing_portal.Session.create(
                customer=sub.stripe_customer_id,
                return_url=settings.FRONTEND_URL + "/settings/billing",
            )
            return Response({"url": session.url})
        except CustomerSubscription.DoesNotExist:
            return Response({"error": "No billing profile found"}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class SubscriptionStatusView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            sub = request.user.subscription
            serializer = CustomerSubscriptionSerializer(sub)
            return Response(serializer.data)
        except CustomerSubscription.DoesNotExist:
            return Response(
                {
                    "active": False,
                    "status": "inactive",
                    "current_period_end": None,
                    "plan_name": None,
                    "stripe_customer_id": None,
                }
            )


class CancelSubscriptionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            sub = request.user.subscription
            if not sub.stripe_subscription_id and not (
                getattr(settings, "TESTING", False)
                or stripe.api_key == "sk_test_mock"
                or not stripe.api_key
            ):
                return Response(
                    {"error": "No active Stripe subscription found"}, status=400
                )

            is_mock = (
                getattr(settings, "TESTING", False)
                or stripe.api_key == "sk_test_mock"
                or not stripe.api_key
            )
            if is_mock:
                sub.status = "canceled"
                sub.active = False
                sub.save()
                return Response({"status": "canceled_locally"})

            # Cancel on Stripe at period end
            stripe.Subscription.modify(
                sub.stripe_subscription_id, cancel_at_period_end=True
            )

            sub.status = "canceled"
            sub.active = False
            sub.save()
            return Response({"status": "canceled_at_period_end"})
        except CustomerSubscription.DoesNotExist:
            return Response({"error": "No active subscription found"}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user).order_by("-created_at")

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)

        # If PDF file is not generated yet, generate it synchronously
        if not invoice.pdf_file:
            from .tasks import generate_invoice_pdf_task

            generate_invoice_pdf_task(invoice.id)
            invoice.refresh_from_db()

        if not invoice.pdf_file:
            return Response({"error": "Invoice PDF generation failed"}, status=500)

        response = FileResponse(
            invoice.pdf_file.open("rb"), content_type="application/pdf"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="invoice_{invoice.stripe_invoice_id or invoice.id}.pdf"'
        )
        return response


from rest_framework import viewsets
from rest_framework.decorators import action
from .models import OrganizationSponsor, Bounty, BountyClaim
from .serializers import (
    OrganizationSponsorSerializer,
    BountySerializer,
    BountyClaimSerializer,
)
from .services import payout_bounty


class OrganizationSponsorViewSet(viewsets.ModelViewSet):
    queryset = OrganizationSponsor.objects.all()
    serializer_class = OrganizationSponsorSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class BountyViewSet(viewsets.ModelViewSet):
    queryset = Bounty.objects.all()
    serializer_class = BountySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def claim(self, request, pk=None):
        bounty = self.get_object()
        if not bounty.is_active:
            return Response({"error": "Bounty is no longer active."}, status=400)

        claim, created = BountyClaim.objects.get_or_create(
            bounty=bounty, user=request.user
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

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def approve_payout(self, request, pk=None):
        claim = self.get_object()
        if claim.is_approved:
            return Response({"error": "Already approved."}, status=400)

        claim = payout_bounty(claim.user, claim.bounty)

        return Response({"status": "payout_processed", "payout_id": claim.payout_id})
