import time
import base64
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from django.conf import settings

# Global in-memory RSA keypair for development/runtime if not configured in settings
_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "atelier-oidc-key-1"


def _int_to_base64(val: int) -> str:
    """Helper to convert integer to urlsafe base64 string without padding."""
    b = val.to_bytes((val.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("utf-8")


def get_private_key_pem() -> bytes:
    pem = getattr(settings, "OIDC_RSA_PRIVATE_KEY_PEM", None)
    if pem:
        return pem.encode("utf-8") if isinstance(pem, str) else pem
    return _RSA_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def get_public_key():
    pem = getattr(settings, "OIDC_RSA_PRIVATE_KEY_PEM", None)
    if pem:
        priv = serialization.load_pem_private_key(
            pem.encode("utf-8") if isinstance(pem, str) else pem, password=None
        )
        return priv.public_key()
    return _RSA_KEY.public_key()


def get_jwks() -> dict:
    pub_key = get_public_key()
    numbers = pub_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": _KID,
                "n": _int_to_base64(numbers.n),
                "e": _int_to_base64(numbers.e),
            }
        ]
    }


def generate_id_token(
    user,
    client_id: str,
    scope: str,
    nonce: str = "",
    issuer: str = "http://localhost:8000",
    expires_in: int = 3600,
) -> str:
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": str(user.id),
        "aud": client_id,
        "exp": now + expires_in,
        "iat": now,
    }

    if nonce:
        payload["nonce"] = nonce

    scopes = scope.split()
    if "profile" in scopes:
        payload["name"] = getattr(user, "get_full_name", lambda: "")() or user.username
        payload["preferred_username"] = user.username
    if "email" in scopes:
        payload["email"] = getattr(user, "email", "")
        payload["email_verified"] = True

    private_pem = get_private_key_pem()
    return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": _KID})
