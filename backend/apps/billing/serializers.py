from rest_framework import serializers
from .models import (
    SubscriptionPlan,
    CustomerSubscription,
    OrganizationSponsor,
    Bounty,
    BountyClaim,
    Invoice,
)


class OrganizationSponsorSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationSponsor
        fields = "__all__"


class BountySerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source="sponsor.name", read_only=True)

    class Meta:
        model = Bounty
        fields = [
            "id",
            "sponsor",
            "sponsor_name",
            "title",
            "description",
            "amount",
            "currency",
            "is_active",
            "created_at",
        ]


class BountyClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = BountyClaim
        fields = "__all__"
        read_only_fields = ["payout_id", "is_approved"]


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ["id", "name", "price", "features", "stripe_price_id"]


class CustomerSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = CustomerSubscription
        fields = [
            "active",
            "status",
            "current_period_end",
            "plan_name",
            "stripe_customer_id",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "stripe_invoice_id",
            "amount",
            "status",
            "pdf_url",
            "created_at",
        ]

    def get_pdf_url(self, obj):
        if obj.pdf_file:
            return obj.pdf_file.url
        return None
