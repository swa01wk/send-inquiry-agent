from app.domain.draft_merge import merge_inquiry_drafts
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source


def test_merge_inquiry_drafts_combines_parallel_field_writes() -> None:
    master = load_master_data()
    base = new_inquiry_draft()

    left, _, _ = write_fields(
        base,
        [(FieldKey.CR_NUMBER.value, "1010123456", Source.USER)],
        master=master,
    )
    right, _, _ = write_fields(
        base,
        [(FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.USER)],
        master=master,
    )

    merged = merge_inquiry_drafts(left, right)
    assert merged.fields[FieldKey.CR_NUMBER].value == "1010123456"
    assert merged.fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"
