"""
Tests for JWT token invalidation on password change.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.jwt import DynamicSaltAccessToken, DynamicSaltRefreshToken


class JWTInvalidationTest(TestCase):
    """
    Test JWT token invalidation on password change.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            password='OldPassword123!',
            email='test@example.com'
        )
        self.client = APIClient()

    def test_access_token_contains_password_hash(self):
        """Test that access token contains password hash."""
        token = DynamicSaltAccessToken.for_user(self.user)
        self.assertIn('password_hash', token)
        self.assertEqual(token['password_hash'], self.user.password[:16])

    def test_refresh_token_contains_password_hash(self):
        """Test that refresh token contains password hash."""
        token = DynamicSaltRefreshToken.for_user(self.user)
        self.assertIn('password_hash', token)
        self.assertEqual(token['password_hash'], self.user.password[:16])

    def test_access_token_valid_before_password_change(self):
        """Test that access token is valid before password change."""
        token = DynamicSaltAccessToken.for_user(self.user)
        # Token should verify without error
        try:
            token.verify()
            verified = True
        except ValueError:
            verified = False
        self.assertTrue(verified)

    def test_access_token_invalid_after_password_change(self):
        """Test that access token becomes invalid after password change."""
        token = DynamicSaltAccessToken.for_user(self.user)
        # Change password
        self.user.set_password('NewPassword456!')
        self.user.save()

        # Token should now be invalid
        with self.assertRaises(ValueError):
            token.verify()

    def test_refresh_token_invalid_after_password_change(self):
        """Test that refresh token becomes invalid after password change."""
        token = DynamicSaltRefreshToken.for_user(self.user)
        # Change password
        self.user.set_password('NewPassword456!')
        self.user.save()

        # Token should now be invalid
        with self.assertRaises(ValueError):
            token.verify()

    def test_api_rejects_old_token_after_password_change(self):
        """Test that API rejects old token after password change."""
        # Login to get token
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)

        # Change password
        self.user.set_password('NewPassword456!')
        self.user.save()

        # Try to access protected endpoint with old token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get('/api/auth/me/')

        # Should be unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_version_increments_on_password_change(self):
        """Test that token version increments on password change."""
        # Get initial version
        if hasattr(self.user, 'profile') and self.user.profile:
            initial_version = self.user.profile.jwt_token_version
        else:
            initial_version = 1

        # Change password
        self.user.set_password('NewPassword456!')
        self.user.save()

        # Get updated version
        self.user.refresh_from_db()
        if hasattr(self.user, 'profile') and self.user.profile:
            new_version = self.user.profile.jwt_token_version
            self.assertGreater(new_version, initial_version)

    def test_token_with_version_mismatch_rejected(self):
        """Test that token with wrong version is rejected."""
        token = DynamicSaltAccessToken.for_user(self.user)

        # Increment version manually
        if hasattr(self.user, 'profile') and self.user.profile:
            self.user.profile.jwt_token_version += 1
            self.user.profile.save()

        # Token should be invalid
        with self.assertRaises(ValueError):
            token.verify()

    def test_change_password_view(self):
        """Test the change password view."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/auth/change-password/',
            {
                'current_password': 'OldPassword123!',
                'new_password': 'NewPassword456!'
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Password changed successfully', response.data['message'])

        # Try to login with old password
        login_response = self.client.post(
            '/api/auth/login/',
            {
                'username': 'testuser',
                'password': 'OldPassword123!'
            }
        )
        self.assertEqual(login_response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Login with new password
        login_response = self.client.post(
            '/api/auth/login/',
            {
                'username': 'testuser',
                'password': 'NewPassword456!'
            }
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_change_password_with_wrong_current_password(self):
        """Test change password with wrong current password."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/auth/change-password/',
            {
                'current_password': 'WrongPassword!',
                'new_password': 'NewPassword456!'
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Current password is incorrect', str(response.data))