import stripe
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings

class CheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {'name': 'Premium Plan'},
                        'unit_amount': 1000,
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url='http://localhost:5173/success',
                cancel_url='http://localhost:5173/cancel',
                metadata={'user_id': request.user.id}
            )
            return Response({'url': session.url})
        except Exception as e:
            return Response({'error': str(e)}, status=400)