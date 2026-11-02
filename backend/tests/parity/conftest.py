import os
import subprocess
import sys
from pathlib import Path

import pytest
from app.config import Settings

pytestmark = pytest.mark.parity


def _parity_backend_params() -> list:
    params = [pytest.param("memory", id="memory")]
    if os.environ.get("TEST_DATABASE_URL"):
        params.append(pytest.param("postgres", id="postgres"))
    return params


def _migrate(database_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    backend_dir = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
    )


@pytest.fixture(params=_parity_backend_params())
def settings(tmp_path: Path, request: pytest.FixtureRequest) -> Settings:
    backend = request.param
    data: dict[str, object] = {
        "upload_dir": str(tmp_path / "uploads"),
        "max_upload_mb": 5,
        "session_ttl_minutes": 120,
        "dev_tools": True,
        "token_secret": "parity-test-secret",
        "email_link_demo": True,
        "state_backend": backend,
    }
    if backend == "postgres":
        url = os.environ.get("TEST_DATABASE_URL")
        if not url:
            pytest.skip("TEST_DATABASE_URL not set")
        _migrate(url)
        data["database_url"] = url
    return Settings(**data)
