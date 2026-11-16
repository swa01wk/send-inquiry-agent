"""Same CR and mall as an open inquiry (chart S15; `duplicate_policy` in policy.yaml).

An inquiry is open from submit until it's rejected, approved or sent to Yardi. A new draft
with the same CR and at least one of the same malls gets one neutral notice in the chat
(`warn`), or can't be submitted (`block`). A skipped CR never matches.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.models import FieldKey, InquiryDraft
from app.workflow.models import Case, CaseStatus

OPEN_STATUSES = frozenset(
    {
        CaseStatus.SUBMITTED,
        CaseStatus.FIRST_REVIEW,
        CaseStatus.REUPLOAD_REQUESTED,
        CaseStatus.SECOND_REVIEW,
        CaseStatus.LEAD_APPROVED,
    }
)


@dataclass(frozen=True)
class OpenDuplicate:
    reference: str
    mall_ids: tuple[str, ...]


def _cr(draft: InquiryDraft) -> str:
    return re.sub(r"\D", "", str(draft.fields[FieldKey.CR_NUMBER].value or ""))


def _malls(draft: InquiryDraft) -> set[str]:
    value = draft.fields[FieldKey.MALLS].value
    return {str(m) for m in value} if isinstance(value, list) else set()


def open_duplicate(cases: Iterable[Case], draft: InquiryDraft) -> OpenDuplicate | None:
    """The newest open case with the draft's CR and a shared mall, or None."""
    cr = _cr(draft)
    malls = _malls(draft)
    if not cr or not malls:
        return None
    own = draft.reference
    matches = [
        case
        for case in cases
        if case.status in OPEN_STATUSES
        and case.reference != own
        and _cr(case.draft) == cr
        and malls & _malls(case.draft)
    ]
    if not matches:
        return None
    newest = max(matches, key=lambda c: c.submitted_at)
    shared = tuple(sorted(malls & _malls(newest.draft)))
    return OpenDuplicate(reference=newest.reference, mall_ids=shared)


def notice_card_id(duplicate: OpenDuplicate) -> str:
    return f"duplicate-{duplicate.reference}"
