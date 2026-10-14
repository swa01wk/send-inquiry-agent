from app.api.cards import document_upload_payload, dotted_allowed_extensions
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data


def test_document_upload_allowed_extensions_are_dotted() -> None:
    assert ".pdf" in dotted_allowed_extensions()
    draft = new_inquiry_draft()
    master = load_master_data()
    payload = document_upload_payload(draft, master, max_mb=5)
    assert ".pdf" in payload.allowed_extensions
