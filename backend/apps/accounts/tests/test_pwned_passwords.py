import hashlib
from unittest.mock import Mock, patch
import pytest
import requests
from django.core.exceptions import ValidationError

from apps.accounts.validators import PwnedPasswordsValidator


class TestPwnedPasswordsValidator:
    def setup_method(self):
        self.validator = PwnedPasswordsValidator(timeout=0.5)

    def test_empty_password_passes(self):
        with patch("requests.get") as mock_get:
            self.validator.validate("")
            self.validator.validate(None)
            mock_get.assert_not_called()

    def test_safe_password_passes(self):
        password = "SuperSecureUniquePassword_9988#@"
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix = sha1[:5]
        suffix = sha1[5:]

        # Mock response that doesn't contain this suffix
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = (
            "0018A45C4D637816E34F11FB8154C86BFA4:2\r\n"
            "00D4F6E8F66CBC10A47200141D3B936B52E:1\r\n"
            "011053FD0102E4F617DA84C02F78333D2EC:12\r\n"
        )

        with patch("requests.get", return_value=mock_response) as mock_get:
            self.validator.validate(password)
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert f"https://api.pwnedpasswords.com/range/{prefix}" in args[0]
            assert kwargs["timeout"] == 0.5

    def test_pwned_password_raises_validation_error(self):
        password = "password123"
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix = sha1[:5]
        suffix = sha1[5:]

        # Mock response containing the suffix
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = (
            f"0018A45C4D637816E34F11FB8154C86BFA4:2\r\n"
            f"{suffix}:123456\r\n"
            f"011053FD0102E4F617DA84C02F78333D2EC:12\r\n"
        )

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(ValidationError) as exc_info:
                self.validator.validate(password)
            assert exc_info.value.code == "password_pwned"
            assert "data breach" in exc_info.value.message.lower()

    def test_timeout_fallback_graceful(self):
        password = "any_password_123"
        with patch("requests.get", side_effect=requests.Timeout("Connection timed out")):
            # Should not raise ValidationError on timeout
            self.validator.validate(password)

    def test_request_exception_fallback_graceful(self):
        password = "any_password_123"
        with patch("requests.get", side_effect=requests.RequestException("Network unreachable")):
            # Should not raise ValidationError on network failure
            self.validator.validate(password)

    def test_non_200_status_code_fallback_graceful(self):
        password = "any_password_123"
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        with patch("requests.get", return_value=mock_response):
            self.validator.validate(password)

    def test_help_text(self):
        help_text = self.validator.get_help_text()
        assert "data breach" in help_text.lower()
