from rest_framework import serializers
from .models import SubscriptionPlan, CustomerSubscription, OrganizationSponsor, Bounty, BountyClaim

class OrganizationSponsorSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationSponsor
        fields = '__all__'

class BountySerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source='sponsor.name', read_only=True)
    
    class Meta:
        model = Bounty
        fields = ['id', 'sponsor', 'sponsor_name', 'title', 'description', 'amount', 'currency', 'is_active', 'created_at']

class BountyClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = BountyClaim
        fields = '__all__'
        read_only_fields = ['payout_id', 'is_approved']
