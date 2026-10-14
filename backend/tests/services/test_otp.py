import logging

import pytest
from app.services.otp import MockOtpService


@pytest.mark.asyncio
async def test_otp_verify_success_and_failure(caplog):
    service = MockOtpService("1234")
    with caplog.at_level(logging.INFO):
        await service.send("sess-1", "user@example.com", "+966501234567")

    assert await service.verify("sess-1", "1234") is True
    assert await service.verify("sess-1", "0000") is False

    assert "1234" not in caplog.text
    assert "OTP sent" in caplog.text
