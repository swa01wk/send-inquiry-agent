"""Mock Yardi: company by CR (demo feedback §3.8, R4)."""

from __future__ import annotations

from pathlib import Path

from app.services.tenants import TenantDirectory
from app.services.yardi import MockYardiService


def _yardi(tmp_path: Path) -> MockYardiService:
    return MockYardiService(str(tmp_path))


def test_company_by_cr_finds_the_tenants_company(tmp_path: Path) -> None:
    yardi = _yardi(tmp_path)
    company = yardi.company_by_cr("1010000000")
    assert company is not None
    assert (company.id, company.name) == ("YC-1301", "Oasis Coffee Company")
    assert company.address == "Prince Sultan Road, Al Rawdah, Jeddah"


def test_company_by_cr_normalises_digits_and_spaces(tmp_path: Path) -> None:
    yardi = _yardi(tmp_path)
    assert yardi.company_by_cr(" ١٠١٠٤٤٤٤٤٤ ") == yardi.company_by_cr("1010444444")
    assert yardi.company_by_cr("1010444444") is not None


def test_company_by_cr_unknown_or_empty_is_none(tmp_path: Path) -> None:
    yardi = _yardi(tmp_path)
    assert yardi.company_by_cr("1019999999") is None
    assert yardi.company_by_cr("") is None


def test_every_tenant_is_linked_to_one_yardi_company(tmp_path: Path) -> None:
    """tenants.json and yardi.json agree: each Tenant Central CR has its Yardi company."""
    yardi = _yardi(tmp_path)
    for tenant in TenantDirectory().all():
        company = yardi.company_by_cr(tenant.cr_number)
        assert company is not None, tenant.id
        assert company.name == tenant.company_name


def test_name_search_still_matches_active_companies_by_first_word(tmp_path: Path) -> None:
    yardi = _yardi(tmp_path)
    assert [c.id for c in yardi.search_companies("Bean Street Trading")] == ["YC-1001", "YC-1002"]
    assert [c.id for c in yardi.search_companies("Oasis")] == ["YC-1301"]
