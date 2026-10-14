from app.services.cr import MockCrService


def test_cr_existing_account():
    result = MockCrService().verify("1010000000")
    assert result.exists is True
    assert result.company_name is None
    assert result.company_address is None


def test_cr_new_with_company_details():
    result = MockCrService().verify("1010123456")
    assert result.exists is False
    assert result.company_name == "Bean Street Trading Co."
    assert result.company_address == "King Fahd Road, Al Olaya, Riyadh"


def test_cr_new_without_details():
    result = MockCrService().verify("1098765432")
    assert result.exists is False
    assert result.company_name is None
    assert result.company_address is None


def test_cr_fawaz_alhokair():
    result = MockCrService().verify("1010222222")
    assert result.exists is False
    assert result.company_name == "Fawaz Alhokair Trading Co."
