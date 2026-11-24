import hashlib
import logging
import requests
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


class PwnedPasswordsValidator:
    """
    Validates that a password has not been exposed in known data breaches
    using the HaveIBeenPwned k-Anonymity API (api.pwnedpasswords.com/range/{prefix}).
    """

    API_URL = "https://api.pwnedpasswords.com/range/{prefix}"
    DEFAULT_TIMEOUT = 0.5  # 500ms fallback timeout

    def __init__(self, timeout=None):
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

    def validate(self, password, user=None):
        if not password:
            return

        sha1_hash = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]

        try:
            response = requests.get(
                self.API_URL.format(prefix=prefix),
                headers={
                    "User-Agent": "Atelier-PwnedPasswordsValidator/1.0",
                    "Add-Padding": "true",
                },
                timeout=self.timeout,
            )
            if response.status_code == 200:
                for line in response.text.splitlines():
                    parts = line.strip().split(":")
                    if parts and parts[0].upper() == suffix:
                        count = parts[1] if len(parts) > 1 else ""
                        raise ValidationError(
                            _(
                                "This password has appeared in a data breach and cannot be used. "
                                "Please choose a different, more secure password."
                            ),
                            code="password_pwned",
                            params={"count": count},
                        )
        except ValidationError:
            raise
        except (requests.RequestException, TimeoutError, OSError) as e:
            # Fallback gracefully on network timeout or external API errors so user registration is not blocked
            logger.warning(
                "PwnedPasswords check failed or timed out: %s. Falling back gracefully.",
                e,
            )
            return
        except Exception as e:
            logger.warning(
                "Unexpected error during PwnedPasswords check: %s. Falling back gracefully.",
                e,
            )
            return

    def get_help_text(self):
        return _("Your password must not have appeared in a publicly known data breach.")
