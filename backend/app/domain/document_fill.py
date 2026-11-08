"""Fill draft fields from an uploaded profile (demo feedback §3.7, D11; ADR-R4).

The document review service reads typed values from the company and brand profiles. Here
they reach the draft:

- an empty field is written with `source: derived`, `confirmed: false` and the evidence
  "<Document label>: <file name>, uploaded <time>", so the applicant confirms it on the
  confirm card before submit (golden rule 2);
- a field that already has a value (typed, derived from the chat, from staff or verified)
  is never overwritten; `document_checks` compares it instead;
- a replaced or removed profile takes back the values it filled, so the new file's values
  are filled and confirmed again.

Only typed values move: no document text reaches the draft, a note or the model.
"""

from __future__ import annotations

from app.domain import draft_ops
from app.domain.fields import document_label
from app.domain.master import MasterData
from app.domain.models import DocType, DocumentRef, FieldKey, FieldValue, InquiryDraft, Source


def document_evidence(ref: DocumentRef) -> str:
    """Shown on the confirm card and in the case brief ("from: Company Profile, …")."""
    when = ref.uploaded_at.strftime("%d %b %Y %H:%M")
    return f"{document_label(ref.doc_type)}: {ref.file_name}, uploaded {when}"


def _is_empty(field: FieldValue) -> bool:
    return field.value in (None, "", [])


def clear_from_document(draft: InquiryDraft, doc_type: DocType) -> InquiryDraft:
    """Take back the values this document filled, before it is replaced or removed.

    Only a value still as the document left it (derived, carrying this document's evidence)
    is cleared; one the applicant has since edited stays.
    """
    ref = draft.documents.get(doc_type)
    if ref is None or not ref.filled_fields:
        return draft
    updated = draft.model_copy(deep=True)
    evidence = document_evidence(ref)
    for key_str in ref.filled_fields:
        try:
            key = FieldKey(key_str)
        except ValueError:
            continue
        field = updated.fields[key]
        if field.source == Source.DERIVED and field.evidence == evidence:
            updated.fields[key] = FieldValue()
    updated.documents[doc_type] = ref.model_copy(update={"filled_fields": []})
    return updated


def fill_from_review(
    draft: InquiryDraft, doc_type: DocType, master: MasterData
) -> tuple[InquiryDraft, list[str]]:
    """Write the review's values into empty fields. Returns the draft and the keys written.

    A value that fails validation (for example a category that isn't in master data) is
    skipped: the agent asks for that field as usual.
    """
    ref = draft.documents.get(doc_type)
    if ref is None or ref.review is None or ref.review.status != "done":
        return draft, []
    entries: list[draft_ops.WriteEntry] = []
    for key_str, extracted in ref.review.fields.items():
        try:
            key = FieldKey(key_str)
        except ValueError:
            continue
        if not _is_empty(draft.fields[key]):
            continue
        entries.append((key_str, extracted.value, Source.DERIVED))
    if not entries:
        return draft, []
    evidence = document_evidence(ref)
    updated, written, _errors = draft_ops.write_fields(
        draft,
        entries,
        master=master,
        evidence={key_str: evidence for key_str, _value, _source in entries},
    )
    written = [key for key in written if key in ref.review.fields]
    if not written:
        return draft, []
    updated.documents[doc_type] = updated.documents[doc_type].model_copy(
        update={"filled_fields": written}
    )
    return updated, written


__all__ = ["clear_from_document", "document_evidence", "fill_from_review"]
