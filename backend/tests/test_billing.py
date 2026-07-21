import json
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import pytest
from apps.billing.models import SubscriptionPlan, CustomerSubscription, Invoice, Payment
from apps.billing.tasks import generate_invoice_pdf_task

User = get_user_model()


@pytest.mark.django_db
class TestBillingSystem:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.user = User.objects.create_user(
            username="billinguser",
            email="billinguser@example.com",
            password="testpassword123",
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Pro Plan",
            stripe_price_id="price_123_pro",
            price=19.99,
            features=["Feature A", "Feature B"],
        )

    def test_plan_list_endpoint(self, api_client):
        url = reverse("plans")
        response = api_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Pro Plan"
        assert data[0]["price"] == "19.99"

    def test_checkout_session_unauthenticated(self, api_client):
        url = reverse("checkout")
        response = api_client.post(url, {"plan_id": self.plan.id})
        assert response.status_code == 401

    def test_checkout_session_mock_success(self, api_client):
        api_client.force_authenticate(user=self.user)
        url = reverse("checkout")
        response = api_client.post(url, {"plan_id": self.plan.id})
        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert "success=true" in data["checkout_url"]

        # Validate database update under mock mode
        sub = CustomerSubscription.objects.get(user=self.user)
        assert sub.active is True
        assert sub.plan == self.plan
        assert sub.status == "active"

    def test_checkout_session_plan_not_found(self, api_client):
        api_client.force_authenticate(user=self.user)
        url = reverse("checkout")
        response = api_client.post(url, {"plan_id": 99999})
        assert response.status_code == 404

    def test_portal_session_mock_success(self, api_client):
        api_client.force_authenticate(user=self.user)
        CustomerSubscription.objects.create(
            user=self.user, stripe_customer_id="cus_mock_123", active=True
        )
        url = reverse("portal")
        response = api_client.post(url)
        assert response.status_code == 200
        data = response.json()
        assert "url" in data

    def test_portal_session_no_subscription(self, api_client):
        api_client.force_authenticate(user=self.user)
        url = reverse("portal")
        response = api_client.post(url)
        assert response.status_code == 400

    def test_subscription_status(self, api_client):
        api_client.force_authenticate(user=self.user)
        url = reverse("status")
        # Pre-subscription status
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.json()["status"] == "inactive"

        # Subscribe
        CustomerSubscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_mock_123",
            stripe_subscription_id="sub_mock_123",
            plan=self.plan,
            active=True,
            status="active",
            current_period_end=timezone.now() + timedelta(days=30),
        )
        response = api_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True
        assert data["plan_name"] == "Pro Plan"
        assert data["status"] == "active"

    def test_webhook_checkout_session_completed(self, api_client):
        payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_12345",
                    "subscription": "sub_12345",
                    "metadata": {"user_id": self.user.id, "plan_id": self.plan.id},
                }
            },
        }
        url = reverse("stripe-webhook")
        response = api_client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        sub = CustomerSubscription.objects.get(user=self.user)
        assert sub.stripe_customer_id == "cus_12345"
        assert sub.stripe_subscription_id == "sub_12345"
        assert sub.plan == self.plan
        assert sub.active is True
        assert sub.status == "active"

    def test_webhook_customer_subscription_deleted(self, api_client):
        sub = CustomerSubscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            plan=self.plan,
            active=True,
            status="active",
        )
        payload = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_123", "customer": "cus_123"}},
        }
        url = reverse("stripe-webhook")
        response = api_client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        sub.refresh_from_db()
        assert sub.active is False
        assert sub.status == "canceled"

    def test_webhook_invoice_paid_creates_records_and_pdf(self, api_client):
        sub = CustomerSubscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            plan=self.plan,
            active=True,
            status="active",
        )
        payload = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_999",
                    "customer": "cus_123",
                    "amount_paid": 1999,  # $19.99 in cents
                    "currency": "usd",
                    "charge": "ch_777",
                }
            },
        }
        url = reverse("stripe-webhook")
        response = api_client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        # Check invoice was created
        invoice = Invoice.objects.get(stripe_invoice_id="in_999", user=self.user)
        assert invoice.amount == 19.99
        assert invoice.status == "paid"

        # In pytest, Q_CLUSTER has "sync": True, so the PDF task runs synchronously
        assert bool(invoice.pdf_file) is True
        assert invoice.pdf_file.name.endswith(".pdf")

        # Check payment was created
        payment = Payment.objects.get(stripe_charge_id="ch_777", user=self.user)
        assert payment.amount == 19.99
        assert payment.currency == "USD"
        assert payment.status == "succeeded"

    def test_webhook_invoice_payment_failed(self, api_client):
        sub = CustomerSubscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            plan=self.plan,
            active=True,
            status="active",
        )
        payload = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_888",
                    "customer": "cus_123",
                    "amount_due": 1999,
                    "currency": "usd",
                }
            },
        }
        url = reverse("stripe-webhook")
        response = api_client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        sub.refresh_from_db()
        assert sub.status == "past_due"
        assert sub.payment_failed_at is not None

        invoice = Invoice.objects.get(stripe_invoice_id="in_888", user=self.user)
        assert invoice.status == "open"

        payment = Payment.objects.get(
            stripe_charge_id="ch_failed_in_888", user=self.user
        )
        assert payment.status == "failed"

    def test_invoice_list_and_download(self, api_client):
        api_client.force_authenticate(user=self.user)
        invoice = Invoice.objects.create(
            user=self.user, stripe_invoice_id="in_555", amount=19.99, status="paid"
        )

        list_url = reverse("invoice-list")
        response = api_client.get(list_url)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["stripe_invoice_id"] == "in_555"

        download_url = reverse("invoice-download", kwargs={"pk": invoice.id})
        download_response = api_client.get(download_url)
        assert download_response.status_code == 200
        assert download_response["Content-Type"] == "application/pdf"
        assert "attachment" in download_response["Content-Disposition"]

    def test_cancel_subscription_endpoint(self, api_client):
        api_client.force_authenticate(user=self.user)
        sub = CustomerSubscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_mock_123",
            stripe_subscription_id="sub_mock_123",
            plan=self.plan,
            active=True,
            status="active",
        )
        url = reverse("cancel")
        response = api_client.post(url)
        assert response.status_code == 200
        assert response.json()["status"] == "canceled_locally"

        sub.refresh_from_db()
        assert sub.active is False
        assert sub.status == "canceled"
