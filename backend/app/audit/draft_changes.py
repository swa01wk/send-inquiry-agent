"""Audit what a turn or action changed in the draft (`field_written`, `field_confirmed`)."""

from __future__ import annotations

from app.audit import HASHED_FIELDS, Actor, AuditLog, value_hash
from app.domain.models import FieldKey, InquiryDraft


def record_draft_changes(
    audit: AuditLog,
    inquiry_id: str,
    before: InquiryDraft,
    after: InquiryDraft,
    *,
    actor: Actor,
    via: str,
) -> None:
    confirmed: list[str] = []
    for key in FieldKey:
        old = before.fields[key]
        new = after.fields[key]
        if new.value != old.value or new.source != old.source:
            payload: dict[str, object] = {
                "key": key.value,
                "source": new.source.value if new.source else None,
                "confirmed": new.confirmed,
            }
            if new.value is not None:
                if key.value in HASHED_FIELDS:
                    payload["value_sha256"] = value_hash(new.value)
                else:
                    payload["display"] = str(new.value)[:80]
            audit.record(inquiry_id, "field_written", actor=actor, payload=payload)
        elif new.confirmed and not old.confirmed:
            confirmed.append(key.value)
    if confirmed:
        audit.record(
            inquiry_id,
            "field_confirmed",
            actor=actor,
            payload={"keys": confirmed, "via": via},
        )
