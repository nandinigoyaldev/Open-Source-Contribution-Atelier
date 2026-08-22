from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.enrollments.models import Enrollment

User = get_user_model()

class DashboardPerformanceTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='teststudent', password='password123')
        self.client.login(username='teststudent', password='password123')
        
        # Create sample related records to test N+1 query elimination
        self.enrollment = Enrollment.objects.create(user=self.user)
        self.url = reverse('dashboard-home') # Adjust URL name as per project urls.py

    def test_dashboard_query_count(self):
        """
        Asserts that loading the dashboard view executes fewer than 5 queries
        using Django's assertNumQueries.
        """
        with self.assertNumQueries(4):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
