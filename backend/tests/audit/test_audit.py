import json

import pytest
from app.audit import AuditLog, redact


def test_redaction_keeps_only_allowed_keys_and_drops_secrets() -> None:
    kept = redact(
        "verification_sent",
        {"channel": "sms", "result": "sent", "code": "1234", "token": "abc", "mobile": "+9665"},
    )
    assert kept == {"channel": "sms", "result": "sent"}


def test_stray_contact_details_are_scrubbed() -> None:
    kept = redact("field_written", {"key": "company_name", "display": "a@b.co +966 50 123 4567"})
    assert kept["display"] == "[email] [number]"


def test_unknown_event_type_is_refused() -> None:
    with pytest.raises(ValueError):
        AuditLog().record("s1", "made_up", actor="system")


def test_events_are_numbered_and_survive_restart(tmp_path) -> None:
    log = AuditLog(str(tmp_path))
    log.record("s1", "inquiry_created", actor="user", payload={"channel": "self_service"})
    log.record("s1", "user_message", actor="user", payload={"chars": 5, "message_id": "u1"})
    reloaded = AuditLog(str(tmp_path)).events("s1")
    assert [e["seq"] for e in reloaded] == [1, 2]
    assert [e["type"] for e in reloaded] == ["inquiry_created", "user_message"]
    assert "u1" in json.dumps(reloaded)
