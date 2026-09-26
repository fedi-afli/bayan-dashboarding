import pytest

from saas.auth import InvalidToken, TokenVerifier
from tests.tokens import AUDIENCE, ISSUER, PUBLIC_KEY, make_token, other_key

verifier = TokenVerifier(ISSUER, AUDIENCE, key_resolver=lambda _: PUBLIC_KEY)


def test_valid_token():
    p = verifier.verify(make_token("alice", "alice@example.tn"))
    assert (p.subject, p.email) == ("alice", "alice@example.tn")


@pytest.mark.parametrize("token", [
    make_token("alice", aud="another-api"),
    make_token("alice", iss="http://evil.test/realms/bayan"),
    make_token("alice", expires_in=-120),
    make_token("alice", key=other_key()),
    "not-a-jwt",
])
def test_rejected_tokens(token):
    with pytest.raises(InvalidToken):
        verifier.verify(token)
