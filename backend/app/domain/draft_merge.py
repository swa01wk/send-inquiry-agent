"""Merge inquiry drafts when multiple tools update state in one graph step."""

from __future__ import annotations

from app.domain.models import FieldKey, FieldValue, InquiryDraft, Source

_SOURCE_RANK: dict[Source | None, int] = {
    Source.VERIFIED: 4,
    Source.USER: 3,
    Source.DERIVED: 2,
    Source.DEFAULT: 1,
    None: 0,
}

_CR_STATUS_RANK: dict[str, int] = {
    "existing": 4,
    "new": 3,
    "skipped": 2,
    "unknown": 1,
}


def _field_has_value(field: FieldValue) -> bool:
    value = field.value
    if value is None:
        return False
    if value == "":
        return False
    if value == []:
        return False
    return True


def _pick_field(left: FieldValue, right: FieldValue) -> FieldValue:
    left_set = _field_has_value(left)
    right_set = _field_has_value(right)
    if not left_set and not right_set:
        return left
    if left_set and not right_set:
        return left
    if right_set and not left_set:
        return right

    left_rank = _SOURCE_RANK.get(left.source, 0)
    right_rank = _SOURCE_RANK.get(right.source, 0)
    if left_rank != right_rank:
        return left if left_rank > right_rank else right
    if left.confirmed != right.confirmed:
        return left if left.confirmed else right
    return right


def merge_inquiry_drafts(left: InquiryDraft, right: InquiryDraft) -> InquiryDraft:
    """Combine two draft snapshots produced from the same pre-step state."""
    merged = left.model_copy(deep=True)
    for key in FieldKey:
        merged.fields[key] = _pick_field(left.fields[key], right.fields[key])

    left_cr = _CR_STATUS_RANK.get(left.cr_status, 0)
    right_cr = _CR_STATUS_RANK.get(right.cr_status, 0)
    if right_cr > left_cr:
        merged.cr_status = right.cr_status

    merged.documents = {**left.documents, **right.documents}
    merged.email_verified = left.email_verified or right.email_verified
    merged.mobile_verified = left.mobile_verified or right.mobile_verified
    merged.email_link_sent_to = right.email_link_sent_to or left.email_link_sent_to
    merged.otp_sent_to = right.otp_sent_to or left.otp_sent_to
    merged.otp_attempts_left = min(left.otp_attempts_left, right.otp_attempts_left)
    merged.terms_accepted = left.terms_accepted or right.terms_accepted
    if right.reference:
        merged.reference = right.reference
    elif left.reference:
        merged.reference = left.reference

    return merged


def merge_cards_shown(left: list[str], right: list[str]) -> list[str]:
    seen = set(left)
    out = list(left)
    for card_id in right:
        if card_id not in seen:
            out.append(card_id)
            seen.add(card_id)
    return out


__all__ = ["merge_cards_shown", "merge_inquiry_drafts"]
