from pathlib import Path

import pytest
from app.config import Settings

pytestmark = pytest.mark.parity


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=5,
        session_ttl_minutes=120,
        dev_tools=True,
        token_secret="parity-test-secret",
        email_link_demo=True,
    )
