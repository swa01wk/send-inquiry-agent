"""Typed values checked against the company and brand profiles (demo feedback §3.7, D12).

The document review service reads a few fields from each profile (`DocumentReview.fields`).
When the applicant typed one of those fields, or the agent derived it from the chat, the two
are compared here. A difference warns the applicant and is shown to the Lease Admin; it never
blocks submit.

The checks are computed from the draft each time instead of being stored, so a value the
applicant corrects later stops being flagged by itself, and one they keep stays flagged.

Comparison ignores case, whitespace and punctuation, normalises Arabic (diacritics, tatweel,
alef, ya and ta marbuta forms, Arabic-Indic digits), and compares sales categories by their
master-data id.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from pydantic import BaseModel

from app.domain.fields import FIELD_BY_KEY, document_label
from app.domain.master import MasterData
from app.domain.models import DocType, FieldKey, InquiryDraft, Source
from app.domain.validation import normalise_digits

# Arabic: harakat, superscript alef, Quranic marks, and tatweel are dropped.
_ARABIC_MARKS = frozenset([chr(c) for c in range(0x064B, 0x0660)] + ["ٰ", "ـ"])
_ARABIC_LETTERS = str.maketrans(
    {
        "أ": "ا",  # أ → ا
        "إ": "ا",  # إ → ا
        "آ": "ا",  # آ → ا
        "ٱ": "ا",  # ٱ → ا
        "ى": "ي",  # ى → ي
        "ة": "ه",  # ة → ه
    }
)


class DocumentMismatch(BaseModel):
    """One field where the profile says something other than the draft."""

    field: str
    label: str
    typed: str
    document_value: str
    doc_type: str
    doc_label: str


def normalise_for_compare(text: str) -> str:
    """Case, whitespace and punctuation ignored; Arabic and digits normalised."""
    folded = unicodedata.normalize("NFKC", normalise_digits(str(text))).casefold()
    folded = folded.translate(_ARABIC_LETTERS)
    kept = []
    for ch in folded:
        if ch in _ARABIC_MARKS or ch.isspace():
            continue
        if unicodedata.category(ch)[0] in ("P", "S"):
            continue
        kept.append(ch)
    return "".join(kept)


def category_id(value: Any, master: MasterData) -> str:
    """A sales category given as an id, an English label or an Arabic label → its id."""
    text = str(value)
    ids = {item.id for item in master.sales_categories}
    if text in ids:
        return text
    wanted = normalise_for_compare(text)
    for item in master.sales_categories:
        labels = [item.label, item.label_ar or ""]
        if any(label and normalise_for_compare(label) == wanted for label in labels):
            return item.id
    return text


def _category_label(category: str, master: MasterData) -> str:
    for item in master.sales_categories:
        if item.id == category:
            return item.label
    return category


def _same(key: FieldKey, draft_value: Any, document_value: str, master: MasterData) -> bool:
    if key == FieldKey.SALES_CATEGORY:
        return category_id(draft_value, master) == category_id(document_value, master)
    return normalise_for_compare(str(draft_value)) == normalise_for_compare(document_value)


def _display(key: FieldKey, value: Any, master: MasterData) -> str:
    if key == FieldKey.SALES_CATEGORY:
        return _category_label(category_id(value, master), master)
    return str(value)


def document_mismatches(
    draft: InquiryDraft,
    master: MasterData,
    *,
    doc_type: DocType | None = None,
) -> list[DocumentMismatch]:
    """Every field where an uploaded profile disagrees with the draft (or only `doc_type`'s).

    A value the same document filled in is not compared with itself. Empty fields and
    documents the service couldn't read (`pending`, `failed`) give nothing.
    """
    out: list[DocumentMismatch] = []
    for current_type, ref in draft.documents.items():
        if doc_type is not None and current_type != doc_type:
            continue
        review = ref.review
        if review is None or review.status != "done" or not review.fields:
            continue
        for key_str, extracted in review.fields.items():
            try:
                key = FieldKey(key_str)
            except ValueError:
                continue
            field = draft.fields.get(key)
            if field is None or field.value in (None, "", []):
                continue
            if key_str in ref.filled_fields and field.source == Source.DERIVED:
                continue  # this document gave the value
            if _same(key, field.value, extracted.value, master):
                continue
            out.append(
                DocumentMismatch(
                    field=key_str,
                    label=FIELD_BY_KEY[key].label,
                    typed=_display(key, field.value, master),
                    document_value=_display(key, extracted.value, master),
                    doc_type=current_type.value,
                    doc_label=document_label(current_type),
                )
            )
    return out


__all__ = [
    "DocumentMismatch",
    "category_id",
    "document_mismatches",
    "normalise_for_compare",
]
