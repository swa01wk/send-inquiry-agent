import re

import pytest
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import Source
from app.services.errors import ReferenceNotFoundError
from app.services.status import MockStatusService
from app.services.submit import MockSubmitService

_REF_RE = re.compile(r"^GEO-(STR|MED|SPC)-\d{6}$")


def test_submit_reference_format_for_each_unit_type():
    master = load_master_data()
    submit = MockSubmitService()
    status = MockStatusService(submit)

    for unit_id, code in [
        ("store", "STR"),
        ("media", "MED"),
        ("specialty", "SPC"),
    ]:
        draft = new_inquiry_draft()
        draft, _, errors = write_fields(
            draft,
            [("unit_type", unit_id, Source.USER)],
            master=master,
        )
        assert not errors
        reference = submit.submit(draft, master)
        assert _REF_RE.match(reference)
        assert f"GEO-{code}-" in reference

        inquiry = status.get(reference)
        assert inquiry.status == "under_review"
        assert inquiry.reference == reference

    unknown = "GEO-STR-999999"
    assert unknown not in submit.submissions
    with pytest.raises(ReferenceNotFoundError):
        status.get(unknown)


def test_same_idempotency_key_returns_same_reference(tmp_path):
    master = load_master_data()
    submit = MockSubmitService(str(tmp_path))
    draft = new_inquiry_draft()
    first = submit.submit(draft, master, idempotency_key="inq:s1:v1")
    again = submit.submit(draft, master, idempotency_key="inq:s1:v1")
    other = submit.submit(draft, master, idempotency_key="inq:s2:v1")
    assert first == again
    assert other != first
    assert submit.lookup("inq:s1:v1") == first
    # A restarted platform still knows the submission.
    reloaded = MockSubmitService(str(tmp_path))
    assert reloaded.lookup("inq:s1:v1") == first
    assert MockStatusService(reloaded).get(first).reference == first


def test_status_names_the_first_review_owner_role():
    master = load_master_data()
    submit = MockSubmitService()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(draft, [("unit_type", "media", Source.USER)], master=master)
    status = MockStatusService(submit).get(submit.submit(draft, master))
    assert status.current_stage == "first_review"
    assert status.owner_role == "Regional Property Leasing Manager (Media)"
    assert status.waiting_on_you == []
