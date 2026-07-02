"""
Tests for distributed tracing and correlation ID functionality.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from config.middleware import get_current_correlation_id
import uuid

class CorrelationIdTest(TestCase):
    """Test correlation ID propagation."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_correlation_id_generation(self):
        """Test that correlation ID is generated for requests."""
        response = self.client.get('/api/health/')
        
        # Check that correlation ID is in response headers
        self.assertIn('X-Correlation-ID', response)
        correlation_id = response['X-Correlation-ID']
        
        # Check format
        self.assertTrue(uuid.UUID(correlation_id))
    
    def test_correlation_id_propagation(self):
        """Test that provided correlation ID is used."""
        test_id = str(uuid.uuid4())
        response = self.client.get(
            '/api/health/',
            headers={'X-Correlation-ID': test_id}
        )
        
        self.assertEqual(response['X-Correlation-ID'], test_id)
    
    def test_logging_with_correlation_id(self):
        """Test that logs include correlation ID."""
        import logging
        logger = logging.getLogger(__name__)
        
        test_id = str(uuid.uuid4())
        with self.settings(MIDDLEWARE=['config.middleware.CorrelationIdMiddleware']):
            response = self.client.get(
                '/api/health/',
                headers={'X-Correlation-ID': test_id}
            )
            
            # Log a message and check it has correlation ID
            with self.assertLogs(logger, level='INFO') as log:
                logger.info("Test log message")
                self.assertIn(test_id, log.output[0])