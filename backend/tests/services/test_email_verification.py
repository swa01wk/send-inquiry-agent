import logging

import pytest
from app.services.email_verification import MockEmailVerificationService


@pytest.mark.asyncio
async def test_email_link_single_use_and_not_logged(caplog):
    service = MockEmailVerificationService()
    with caplog.at_level(logging.INFO):
        await service.send_link("sess-1", "sara@beanstreet.example")
    token = service.demo_token("sess-1")
    assert token
    assert token not in caplog.text
    assert "Email verification link sent" in caplog.text

    assert (await service.verify("sess-1", "wrong")).verified_email is None
    check = await service.verify("sess-1", token)
    assert check.verified_email == "sara@beanstreet.example"
    # Single use
    assert (await service.verify("sess-1", token)).verified_email is None


@pytest.mark.asyncio
async def test_new_link_replaces_old_one():
    service = MockEmailVerificationService()
    await service.send_link("sess-1", "old@example.com")
    old = service.demo_token("sess-1")
    await service.send_link("sess-1", "new@example.com")
    assert old is not None
    assert (await service.verify("sess-1", old)).verified_email is None
    new = service.demo_token("sess-1")
    assert new is not None
    assert (await service.verify("sess-1", new)).verified_email == "new@example.com"
