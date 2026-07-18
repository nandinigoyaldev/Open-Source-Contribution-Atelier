from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import stripe
from django.conf import settings

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None
    endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', 'whsec_test_mock')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event.type == 'checkout.session.completed':
        session = event.data.object
        # Handle successful checkout
    elif event.type == 'customer.subscription.deleted':
        subscription = event.data.object
        # Handle cancelled subscription

    return HttpResponse(status=200)
