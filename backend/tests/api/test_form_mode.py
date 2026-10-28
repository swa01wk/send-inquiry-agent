"""Form mode: the inquiry can be finished without the model (L3 §3.14, framework L1)."""

from pathlib import Path

import pytest
from app.agent.events import FORM_MODE_RESUME_NOTE, FORM_MODE_STILL_DOWN
from app.agent.form_mode import FORM_MODE_NOTICE
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel, model_error_kind
from app.config import Settings
from app.domain.models import FieldKey
from tests.scenarios.helpers import chat_action, chat_message, token_text, ui_cards, upload_document

EMAIL = "sara@beanstreet.example"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(upload_dir=str(tmp_path / "uploads"), max_upload_mb=5, dev_tools=True)


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "Welcome back, let's carry on."}] * 4)


async def _session(client) -> str:
    created = await client.post("/api/sessions")
    return created.json()["session_id"]


def _form_card(events) -> dict:
    cards = ui_cards(events, "form_mode")
    assert cards, "expected a form_mode card"
    return cards[-1]["payload"]


async def _audit_types(client, session_id: str) -> list[str]:
    events = (await client.get(f"/api/dev/audit/{session_id}")).json()["events"]
    return [e["type"] for e in events]


async def test_two_model_failures_switch_to_form_mode(client, app) -> None:
    session_id = await _session(client)
    app.state.services.gateway.set_session_faults(session_id, "llm:unavailable:2")

    events = await chat_message(client, session_id, "Hi, we'd like a kiosk")
    assert token_text(events) == FORM_MODE_NOTICE
    payload = _form_card(events)
    assert payload["active"] is True
    assert payload["next_step"] == "cr"
    assert payload["can_skip_cr"] is True
    assert events[-1][0] == "done"
    assert not [e for e in events if e[0] == "error"]

    session = await app.state.session_store.get(session_id)
    assert session.form_mode is True
    assert "form_mode_entered" in await _audit_types(client, session_id)


async def test_one_model_failure_is_retried_in_the_same_turn(client, app) -> None:
    session_id = await _session(client)
    app.state.services.gateway.set_session_faults(session_id, "llm:timeout:1")
    events = await chat_message(client, session_id, "Hello")
    assert token_text(events) == "Welcome back, let's carry on."
    assert not ui_cards(events, "form_mode")
    assert (await app.state.session_store.get(session_id)).form_mode is False


async def test_finish_and_submit_in_form_mode_then_the_chat_carries_on(client, app) -> None:
    session_id = await _session(client)
    app.state.services.gateway.set_session_faults(session_id, "llm:unavailable:2")
    await chat_message(client, session_id, "Hi")

    # CR: skip. The form lists what's missing; no agent turn runs for actions.
    events = await chat_action(client, session_id, "cr_skip")
    assert not token_text(events)
    payload = _form_card(events)
    assert payload["next_step"] == "details"
    keys = [f["key"] for f in payload["fields"]]
    assert keys == [
        "company_name",
        "company_address",
        "brand_name_en",
        "brand_name_ar",
        "unit_type",
        "sales_category",
        "first_name",
        "last_name",
        "email",
        "contact_number",
    ]
    assert payload["fields"][4]["kind"] == "select"
    assert payload["fields"][4]["master_kind"] == "unit_types"
    picker = ui_cards(events, "mall_picker")[0]["payload"]
    assert picker["city"]["id"] == "all"
    assert len(picker["malls"]) == 20

    values = {
        "company_name": "Bean Street Trading Co.",
        "company_address": "King Fahd Road, Al Olaya, Riyadh",
        "brand_name_en": "Bean Street",
        "brand_name_ar": "بين ستريت",
        "unit_type": "specialty",
        "sales_category": "fnb_cafe",
        "first_name": "Sara",
        "last_name": "Ali",
        "email": EMAIL,
        "contact_number": "٠٥٠١٢٣٤٥٦٧",
    }
    for key, value in values.items():
        events = await chat_action(client, session_id, "edit_field", {"key": key, "value": value})
        assert not token_text(events)
    assert _form_card(events)["fields"] == []

    # Mall, then verification is sent without the model.
    events = await chat_action(client, session_id, "select_malls", {"mall_ids": ["riyadh-mall-a"]})
    assert _form_card(events)["next_step"] == "verification"
    assert ui_cards(events, "verification")
    outbox = app.state.services.notifications.messages(to=EMAIL)
    assert [m["template"] for m in outbox] == ["email_verification_link"]

    token = app.state.services.email_verification.demo_token(session_id)
    await chat_action(client, session_id, "verify_email", {"token": token})
    events = await chat_action(client, session_id, "submit_otp", {"code": "1234"})
    assert _form_card(events)["next_step"] == "documents"
    assert ui_cards(events, "document_upload")

    for doc_type in ("company_profile", "brand_profile"):
        uploaded = await upload_document(client, session_id, doc_type, f"{doc_type}.pdf", b"%PDF")
        assert uploaded["status_code"] == 200
    events = await chat_action(client, session_id, "documents_updated")
    assert _form_card(events)["next_step"] == "review"
    assert ui_cards(events, "review")[0]["payload"]["blockers"] == ["terms_not_accepted"]

    events = await chat_action(client, session_id, "accept_and_submit", {"terms_accepted": True})
    assert ui_cards(events, "success")
    assert _form_card(events)["next_step"] == "submitted"
    session = await app.state.session_store.get(session_id)
    assert session.draft.reference
    assert session.draft.fields[FieldKey.MOBILE].value == "+966501234567"

    # The model is back: the chat carries on and the card says so.
    events = await chat_message(client, session_id, "Thanks! One more question")
    assert token_text(events) == "Welcome back, let's carry on."
    back = _form_card(events)
    assert back["active"] is False
    assert session.form_mode is False
    assert "form_mode_left" in await _audit_types(client, session_id)
    snapshot = await app.state.graph.aget_state({"configurable": {"thread_id": session_id}})
    texts = [str(m.content) for m in snapshot.values["messages"]]
    assert FORM_MODE_RESUME_NOTE in texts


async def test_cr_check_from_the_form(client, app) -> None:
    session_id = await _session(client)
    app.state.services.gateway.set_session_faults(session_id, "llm:unavailable:2")
    await chat_message(client, session_id, "Hi")
    events = await chat_action(client, session_id, "cr_check", {"cr_number": "١٠١٠١٢٣٤٥٦"})
    confirm = ui_cards(events, "confirm_fields")
    assert confirm and confirm[0]["payload"]["title"] == "From your CR — please confirm"
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "new"
    assert session.draft.fields[FieldKey.CR_NUMBER].value == "1010123456"
    assert _form_card(events)["next_step"] == "details"

    events = await chat_action(client, session_id, "cr_check", {"cr_number": "123"})
    assert _form_card(events)["next_step"] == "details"  # already done: nothing changes


async def test_still_down_keeps_form_mode(client, app) -> None:
    session_id = await _session(client)
    app.state.services.gateway.set_session_faults(session_id, "llm:unavailable")
    await chat_message(client, session_id, "Hi")
    events = await chat_message(client, session_id, "Hello again?")
    assert token_text(events) == FORM_MODE_STILL_DOWN
    assert _form_card(events)["active"] is True
    assert (await _audit_types(client, session_id)).count("form_mode_entered") == 1


async def test_form_mode_setting_never_calls_the_model(tmp_path: Path) -> None:
    from tests.scenarios.helpers import scenario_client

    settings = Settings(upload_dir=str(tmp_path / "u"), form_mode=True)
    async with scenario_client(settings, [{"content": "should not be used"}]) as (client, app):
        session_id = await _session(client)
        events = await chat_message(client, session_id, "Hi")
        assert token_text(events) == FORM_MODE_NOTICE
        assert (await app.state.session_store.get(session_id)).script_step == 0


def test_provider_errors_count_as_model_unavailable() -> None:
    class APITimeoutError(Exception):
        __module__ = "openai._exceptions"

    class APIConnectionError(Exception):
        __module__ = "openai._exceptions"

    class ConnectError(Exception):
        __module__ = "httpx._exceptions"

    assert model_error_kind(APITimeoutError()) == "timeout"
    assert model_error_kind(APIConnectionError()) == "unavailable"
    assert model_error_kind(ConnectError()) == "unavailable"
    assert model_error_kind(ValueError("our bug")) is None


class _ProviderDown(Exception):
    __module__ = "openai._exceptions"


class _FlakyModel(ScriptedChatModel):
    """Answers the first `ok_calls` calls from the script, then the provider is down."""

    ok_calls: int = 1

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[override]
        if self._step_index >= self.ok_calls:
            raise _ProviderDown("down")
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


BRAND = {"key": "brand_name_en", "value": "Bean Street", "source": "user"}


async def test_values_saved_before_the_failure_are_kept(tmp_path: Path) -> None:
    from tests.scenarios.helpers import scenario_client

    steps = [
        {
            "content": "",
            "tool_calls": [
                {
                    "name": "update_draft",
                    "args": {"fields": [BRAND]},
                    "id": "t1",
                    "type": "tool_call",
                }
            ],
        }
    ]
    settings = Settings(upload_dir=str(tmp_path / "u"))
    async with scenario_client(settings, steps) as (client, app):
        app.state.graph = build_graph(model_factory=lambda: _FlakyModel(steps=steps, ok_calls=1))
        session_id = await _session(client)
        events = await chat_message(client, session_id, "Our brand is Bean Street")
        assert token_text(events) == FORM_MODE_NOTICE
        session = await app.state.session_store.get(session_id)
        assert session.form_mode is True
        assert session.draft.fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"


async def test_a_bug_is_still_an_error_not_form_mode(tmp_path: Path) -> None:
    from tests.scenarios.helpers import scenario_client

    class _Broken(ScriptedChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[override]
            raise ValueError("bug")

    settings = Settings(upload_dir=str(tmp_path / "u"))
    async with scenario_client(settings, []) as (client, app):
        app.state.graph = build_graph(model_factory=lambda: _Broken(steps=[]))
        session_id = await _session(client)
        events = await chat_message(client, session_id, "Hi")
        assert [name for name, _ in events if name == "error"]
        assert (await app.state.session_store.get(session_id)).form_mode is False
