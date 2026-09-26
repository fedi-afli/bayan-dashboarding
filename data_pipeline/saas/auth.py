"""
Access-token verification. The identity provider (Keycloak locally) owns
passwords, sign-up, sessions; the API only checks the bearer token it
issued: signature (from the provider's published keys), issuer, audience,
expiry. Works with any OIDC provider — nothing Keycloak-specific here.
"""

from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Optional

import httpx
import jwt


class InvalidToken(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    email: Optional[str]
    name: Optional[str]


class TokenVerifier:
    def __init__(self, issuer: str, audience: str, key_resolver: Optional[Callable[[str], object]] = None):
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self._key_resolver = key_resolver

    @cached_property
    def _jwks(self) -> jwt.PyJWKClient:
        discovery = httpx.get(f"{self.issuer}/.well-known/openid-configuration", timeout=10).json()
        return jwt.PyJWKClient(discovery["jwks_uri"], cache_keys=True, lifespan=3600)

    def _key_for(self, token: str):
        if self._key_resolver:
            return self._key_resolver(token)
        return self._jwks.get_signing_key_from_jwt(token).key

    def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._key_for(token),
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
                leeway=10,
            )
        except (jwt.PyJWTError, httpx.HTTPError, KeyError) as e:
            raise InvalidToken(str(e))
        name = claims.get("name") or " ".join(
            p for p in (claims.get("given_name"), claims.get("family_name")) if p
        ) or None
        return Principal(subject=claims["sub"], email=claims.get("email"), name=name)
