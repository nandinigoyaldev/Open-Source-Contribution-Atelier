import stripe
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.billing.models import CustomerSubscription


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JsonResponse({"error": "Invalid payload"}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({"error": "Invalid signature"}, status=400)

    # Handle events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # Sync subscription
        CustomerSubscription.objects.update_or_create(
            stripe_customer_id=session["customer"],
            defaults={
                "stripe_subscription_id": session.get("subscription"),
                "status": "active",
                "user_id": session["metadata"].get("user_id"),
            },
        )

    return JsonResponse({"status": "success"})
