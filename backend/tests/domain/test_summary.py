from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.models import Source
from app.domain.summary import build_draft_summary, prompt_summary


def test_build_draft_summary_snapshot(master):
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [
            ("company_name", "Bean Street Trading Co.", Source.VERIFIED),
            ("company_address", "King Fahd Road, Riyadh", Source.VERIFIED),
        ],
        master=master,
    )
    draft.cr_status = "new"
    summary = build_draft_summary(
        draft,
        master,
        changed_keys=["company_name", "company_address"],
    )
    payload = summary.model_dump()
    assert payload["phase"] == "collecting"
    assert payload["can_submit"] is False
    assert payload["changed_keys"] == ["company_name", "company_address"]
    assert payload["checks"]["required_filled"] == 2
    assert payload["checks"]["unconfirmed"] == 2
    company_rows = [r for r in payload["fields"] if r["group"] == "company"]
    assert company_rows[0]["key"] == "cr_number"
    area_row = next(r for r in payload["fields"] if r["key"] == "area")
    assert area_row["display"] == "10 – 25000 sqm"


def test_prompt_summary_contains_dynamic_lines(master):
    draft = new_inquiry_draft()
    text = prompt_summary(draft, master)
    assert text.startswith("Current phase: gate")
    assert "Missing required:" in text
    assert "Email verified: no" in text
    assert "Mobile verified: not needed (no mobile)" in text
