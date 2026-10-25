import pytest
from app.config import Settings
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def scripted_settings(tmp_path) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=5,
        agent_mode="scripted",
    )


@pytest.fixture
def openai_settings(tmp_path) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=5,
        agent_mode="openai",
    )


@pytest.mark.asyncio
async def test_unknown_scenario_header_is_ignored(app, client, settings):
    settings.agent_mode = "scripted"
    app.state.settings = settings
    res = await client.post("/api/sessions", headers={"X-Test-Scenario": "../evil"})
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    session = await app.state.session_store.get(session_id)
    assert session.test_scenario is None


@pytest.mark.asyncio
async def test_valid_scenario_header_is_stored(app, client, settings):
    settings.agent_mode = "scripted"
    app.state.settings = settings
    res = await client.post("/api/sessions", headers={"X-Test-Scenario": "01-shop-owner"})
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    session = await app.state.session_store.get(session_id)
    assert session.test_scenario == "01-shop-owner"


@pytest.mark.asyncio
async def test_scenario_header_ignored_in_openai_mode(openai_settings):
    from app.agent.graph import build_graph
    from app.agent.model import ScriptedChatModel
    from app.main import create_app
    from app.services.container import build_services
    from app.sessions import SessionStore

    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=[{"content": "OK"}])

    application = create_app(settings=openai_settings, model_factory=factory)
    application.state.settings = openai_settings
    application.state.session_store = SessionStore(ttl_minutes=openai_settings.session_ttl_minutes)
    application.state.services = build_services(openai_settings)
    application.state.graph = build_graph(model_factory=factory)

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        res = await http.post("/api/sessions", headers={"X-Test-Scenario": "01-shop-owner"})
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        session = await application.state.session_store.get(session_id)
        assert session.test_scenario is None
