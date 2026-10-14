import pytest
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import Source


@pytest.fixture
def master():
    return load_master_data()


@pytest.fixture
def empty_draft():
    return new_inquiry_draft()


def fill_minimal_collectible(draft, master):
    entries = [
        ("company_name", "Bean Street Trading Co.", Source.USER),
        ("company_address", "King Fahd Road, Al Olaya, Riyadh", Source.USER),
        ("brand_name_en", "Bean Street", Source.USER),
        ("brand_name_ar", "بين ستريت", Source.USER),
        ("unit_type", "store", Source.USER),
        ("sales_category", "fnb_cafe", Source.USER),
        ("malls", ["riyadh-mall-a"], Source.USER),
        ("first_name", "Sara", Source.USER),
        ("last_name", "Ali", Source.USER),
        ("email", "sara@beanstreet.example", Source.USER),
        ("contact_number", "+966501234567", Source.USER),
    ]
    draft, _, errors = write_fields(draft, entries, master=master)
    assert not errors
    draft.cr_status = "skipped"
    return draft
