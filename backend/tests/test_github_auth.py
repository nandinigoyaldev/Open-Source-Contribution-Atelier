from django.test import TestCase
from github.auth import GitHubAppAuth, get_github_token
from unittest.mock import patch, MagicMock


class GithubAuthTest(TestCase):
    def setUp(self):
        self.auth = GitHubAppAuth()

    @patch("github.auth.jwt.encode")
    def test_generate_jwt(self, mock_jwt):
        """Test JWT generation"""
        mock_jwt.return_value = "test_jwt"
        token = self.auth.generate_jwt()
        self.assertEqual(token, "test_jwt")

    @patch("github.auth.requests.post")
    def test_get_installation_token(self, mock_post):
        """Test installation token retrieval"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "token": "test_token",
            "expires_at": "2025-01-01T00:00:00Z",
        }
        mock_post.return_value = mock_response

        token = self.auth.get_installation_token()
        self.assertEqual(token, "test_token")
