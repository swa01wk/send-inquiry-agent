from collections.abc import Callable
from pathlib import Path

import pytest
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel, get_chat_model
from app.config import Settings, get_settings
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from httpx import ASGITransport, AsyncClient
from langchain_core.language_models.chat_models import BaseChatModel


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=5,
        session_ttl_minutes=120,
    )


@pytest.fixture
def model_factory() -> Callable[[], BaseChatModel] | None:
    return None


def _default_chat_model_factory() -> Callable[[], BaseChatModel]:
    try:
        get_settings().require_openai()
    except RuntimeError:
        return lambda: ScriptedChatModel(steps=[{"content": "OK"}])
    return get_chat_model


@pytest.fixture
def app(settings: Settings, model_factory: Callable[[], BaseChatModel] | None):
    factory = model_factory or _default_chat_model_factory()
    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=settings.session_ttl_minutes)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
