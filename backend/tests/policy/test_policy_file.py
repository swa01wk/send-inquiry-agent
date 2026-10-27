"""Loading and validating the policy file (L3 §3.7)."""

from pathlib import Path

import pytest
from app.config import Settings
from app.domain.models import DocType
from app.policy.config import DEFAULT_POLICY_PATH, PolicyError, load_policy

_DEFAULT_TEXT = DEFAULT_POLICY_PATH.read_text(encoding="utf-8")


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "policy.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_default_policy_matches_poc_assumptions() -> None:
    policy = load_policy()
    assert policy.product_lines == ["store", "media", "specialty"]
    assert policy.existing_tenant_policy == "sign_in"
    assert policy.max_malls_per_inquiry == 1
    assert policy.phone.allowed_countries == "any"
    assert (policy.verification.email, policy.verification.mobile) == ("link", "otp")
    assert (policy.resend.cooldown_seconds, policy.resend.max_per_hour) == (60, 5)
    assert policy.documents.required == [DocType.COMPANY_PROFILE, DocType.BRAND_PROFILE]
    assert policy.duplicate_policy == "warn"
    assert policy.follow_on_reuse_hours == 24


def test_missing_file_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="not found"):
        load_policy(tmp_path / "nope.yaml")


def test_invalid_yaml_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="not valid YAML"):
        load_policy(_write(tmp_path, "product_lines: [store\n"))


@pytest.mark.parametrize(
    ("replace", "with_text", "message"),
    [
        (
            "existing_tenant_policy: sign_in",
            "existing_tenant_policy: maybe",
            "existing_tenant_policy",
        ),
        ("max_malls_per_inquiry: 1", "max_malls_per_inquiry: 0", "max_malls_per_inquiry"),
        ("  mobile: otp", "  mobile: whatsapp", "verification.mobile"),
        ("allowed_countries: any", "allowed_countries: [uk]", "calling code"),
        (
            "required: [company_profile, brand_profile]",
            "required: [company_profile]",
            "missing brand_profile",
        ),
        ("duplicate_policy: warn", "duplicate_policy: ignore", "duplicate_policy"),
        ("follow_on_reuse_hours: 24", "follow_on_reuse_hours: 24\nsurprise: 1", "surprise"),
    ],
)
def test_invalid_values_name_the_rule(
    tmp_path: Path, replace: str, with_text: str, message: str
) -> None:
    assert replace in _DEFAULT_TEXT
    path = _write(tmp_path, _DEFAULT_TEXT.replace(replace, with_text))
    with pytest.raises(PolicyError, match=message):
        load_policy(path)


def test_bad_policy_stops_the_app(tmp_path: Path) -> None:
    from app.main import create_app

    path = _write(
        tmp_path, _DEFAULT_TEXT.replace("max_malls_per_inquiry: 1", "max_malls_per_inquiry: -3")
    )
    with pytest.raises(PolicyError, match="max_malls_per_inquiry"):
        create_app(settings=Settings(policy_path=str(path), upload_dir=str(tmp_path / "u")))


def test_product_line_missing_from_master_data_stops_the_app(tmp_path: Path) -> None:
    from app.main import create_app

    path = _write(
        tmp_path,
        _DEFAULT_TEXT.replace("[store, media, specialty]", "[store, media, specialty, office]"),
    )
    with pytest.raises(PolicyError, match="office"):
        create_app(settings=Settings(policy_path=str(path), upload_dir=str(tmp_path / "u")))
