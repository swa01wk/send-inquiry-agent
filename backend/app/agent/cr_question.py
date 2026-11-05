"""The public page's CR question (demo feedback §3.1, day R1).

Under `public_cr_check: ask_then_sign_in` the self-service chat asks "Do you have a CR?"
and never takes, looks up or repeats a CR number:
- **Yes** → sign in to Tenant Central (Leasing Opportunities); nothing more is collected.
- **No** → the inquiry carries on in chat; company name and address are asked for.

Shared by the `cr_answer` UI action, the `record_cr_answer` tool and the scrubber that runs
on every self-service message before it reaches the history, the audit trail or the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models import InquiryDraft
from app.domain.validation import normalise_digits
from app.policy.config import get_policy

SELF_SERVICE = "self_service"
CR_REMOVED = "[CR number removed]"
CR_TYPED_NOTE = (
    "[guard] cr_number_typed: the user typed a CR number. It was not saved or checked, and "
    "must not be repeated. Reply in one or two warm sentences that signing in is the "
    "quickest way when the company already has a CR (its details are on file there), and "
    "point to the Sign in button. Don't ask for any other details."
)

# A CR number: ten digits on their own, not starting with 0 (Saudi local phone numbers do),
# and not part of a longer number (an international phone number, an IBAN). Arabic-Indic
# and Eastern Arabic digits are normalised first. A ten-digit National ID typed in the chat
# matches too; it isn't needed in chat (the documents card takes it), so that's accepted.
_CR_RE = re.compile(r"(?<![\d+])[1-9]\d{9}(?!\d)")


def cr_question_active(*, assisted: bool, channel: str | None) -> bool:
    """The public page asks the CR question instead of looking a CR up."""
    if assisted or (channel or SELF_SERVICE) != SELF_SERVICE:
        return False
    return get_policy().public_cr_check == "ask_then_sign_in"


def scrub_cr_numbers(text: str) -> tuple[str, bool]:
    """Replace CR-format numbers with a placeholder. Returns (text, found)."""
    # Digit normalisation maps one character to one, so spans found in the normalised text
    # line up with the original, which is kept as typed apart from the removed numbers.
    spans = [m.span() for m in _CR_RE.finditer(normalise_digits(text))]
    if not spans:
        return text, False
    out: list[str] = []
    last = 0
    for start, end in spans:
        out.append(text[last:start])
        out.append(CR_REMOVED)
        last = end
    out.append(text[last:])
    return "".join(out), True


def contains_cr_number(text: str) -> bool:
    return bool(_CR_RE.search(normalise_digits(text)))


@dataclass
class CrAnswer:
    draft: InquiryDraft
    changed: list[str]
    note: str  # the [ui_event] note for the agent


def apply_cr_answer(draft: InquiryDraft, has_cr: bool) -> CrAnswer | None:
    """The draft after the applicant's answer, or None if the CR step is already done.

    Yes uses `cr_status: existing` (stop collecting, sign in) without a CR number; No uses
    `skipped` (company name and address are collected as on the skip path)."""
    if draft.cr_status != "unknown":
        return None
    updated = draft.model_copy(deep=True)
    updated.cr_status = "existing" if has_cr else "skipped"
    note = "[ui_event] cr_answer yes" if has_cr else "[ui_event] cr_answer no"
    return CrAnswer(draft=updated, changed=["cr_status"], note=note)
