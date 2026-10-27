import time

import pytest
from app.security import tokens

SECRET = "test-secret"


def test_round_trip_keeps_subject_and_data() -> None:
    token, claims = tokens.issue(SECRET, "track", "GEO-STR-123456", ttl_seconds=60, data={"i": "s"})
    read = tokens.read(SECRET, token, "track")
    assert read.subject == "GEO-STR-123456"
    assert read.data == {"i": "s"}
    assert read.nonce == claims.nonce


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t[:-3] + "abc",  # signature tampered
        lambda t: "x" + t,  # body tampered
        lambda t: t.replace(".", ""),  # no signature
        lambda _t: "",
    ],
)
def test_tampered_tokens_are_invalid(mutate) -> None:
    token, _ = tokens.issue(SECRET, "resume", "s1", ttl_seconds=60)
    with pytest.raises(tokens.TokenError) as exc:
        tokens.read(SECRET, mutate(token), "resume")
    assert exc.value.code == "token_invalid"


def test_wrong_secret_or_purpose_is_invalid() -> None:
    token, _ = tokens.issue(SECRET, "resume", "s1", ttl_seconds=60)
    with pytest.raises(tokens.TokenError, match="token_invalid"):
        tokens.read("other-secret", token, "resume")
    with pytest.raises(tokens.TokenError, match="token_invalid"):
        tokens.read(SECRET, token, "track")


def test_expired_token() -> None:
    token, _ = tokens.issue(SECRET, "verify_email", "s1", ttl_seconds=60)
    with pytest.raises(tokens.TokenError) as exc:
        tokens.read(SECRET, token, "verify_email", now=time.time() + 61)
    assert exc.value.code == "token_expired"


def test_claims_carry_no_contact_details() -> None:
    token, _ = tokens.issue(
        SECRET,
        "verify_email",
        "s1",
        ttl_seconds=60,
        data={"e": tokens.fingerprint("sara@beanstreet.example")},
    )
    import base64

    body = token.split(".")[0]
    decoded = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
    assert "sara" not in decoded
    assert "beanstreet" not in decoded
