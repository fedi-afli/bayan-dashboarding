"""Test identity provider: an RSA key pair that signs tokens like Keycloak would."""
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "http://idp.test/realms/bayan"
AUDIENCE = "bayan-api"

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY = _key.public_key()


def make_token(sub: str, email: str = None, *, aud: str = AUDIENCE, iss: str = ISSUER,
               expires_in: int = 300, key=None) -> str:
    now = int(time.time())
    claims = {"sub": sub, "email": email or f"{sub}@example.test", "name": sub.title(),
              "aud": aud, "iss": iss, "iat": now, "exp": now + expires_in}
    return jwt.encode(claims, key or _key, algorithm="RS256")


def other_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)
