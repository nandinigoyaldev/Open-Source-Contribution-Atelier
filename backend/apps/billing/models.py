from django.db import models
from django.conf import settings

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    stripe_price_id = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.JSONField(default=list)

    def __str__(self):
        return self.name

class CustomerSubscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription', null=True, blank=True)
    # If organizations exist, we can optionally link it here as well
    # organization = models.OneToOneField('organizations.Organization', on_delete=models.CASCADE, null=True, blank=True)
    
    stripe_customer_id = models.CharField(max_length=100, unique=True)
    stripe_subscription_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    active = models.BooleanField(default=False)
    current_period_end = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Subscription for {self.user}"
