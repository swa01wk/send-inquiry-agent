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
