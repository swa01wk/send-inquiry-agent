"""Evidence for derived values (L3 §3.9): the user's words, on the card and in the audit."""

from app.agent.state import initial_agent_state
from app.agent.tools import update_draft
from app.audit import AuditLog
from app.audit.draft_changes import record_draft_changes
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from langchain_core.messages import HumanMessage
from tests.agent.conftest import make_tool_runtime

USER = "Hi, we run a Specialty  Coffee kiosk called Bean Street"


def _state(text: str = USER):
    state = initial_agent_state(session_id="s", draft=new_inquiry_draft(), phase="collecting")
    state["messages"] = [HumanMessage(content=text)]
    return state


def _invoke(agent_runtime, writer, fields, text: str = USER):
    state = _state(text)
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    return update_draft.invoke({"fields": fields, "state": state, "runtime": runtime})


def test_evidence_quoting_the_user_is_kept_and_shown(agent_runtime, stream_events) -> None:
    events, writer = stream_events
    result = _invoke(
        agent_runtime,
        writer,
        [
            {
                "key": "unit_type",
                "value": "specialty",
                "source": "derived",
                "evidence": "“specialty coffee kiosk”",
            }
        ],
    )
    field = result.update["draft"].fields[FieldKey.UNIT_TYPE]
    assert field.source == Source.DERIVED
    assert field.evidence == "specialty coffee kiosk"
    cards = [e["data"] for e in events if e.get("type") == "ui_card"]
    row = next(r for r in cards[-1]["payload"]["fields"] if r["key"] == "unit_type")
    assert row["evidence"] == "specialty coffee kiosk"


def test_evidence_the_user_never_wrote_is_dropped(agent_runtime, stream_events) -> None:
    _events, writer = stream_events
    result = _invoke(
        agent_runtime,
        writer,
        [
            {
                "key": "unit_type",
                "value": "specialty",
                "source": "derived",
                "evidence": "a small booth",
            }
        ],
    )
    field = result.update["draft"].fields[FieldKey.UNIT_TYPE]
    assert field.value == "specialty"  # the value is still saved for the user to confirm
    assert field.evidence is None
    assert "Evidence ignored" in result.update["messages"][0].content


def test_evidence_only_for_derived_values(agent_runtime, stream_events) -> None:
    _events, writer = stream_events
    result = _invoke(
        agent_runtime,
        writer,
        [{"key": "brand_name_en", "value": "Bean Street", "source": "user", "evidence": "Bean"}],
    )
    assert result.update["draft"].fields[FieldKey.BRAND_NAME_EN].evidence is None


def test_evidence_is_capped_at_80_characters(agent_runtime, stream_events) -> None:
    long_text = "we sell " + "very " * 30 + "fine coffee"
    _events, writer = stream_events
    result = _invoke(
        agent_runtime,
        writer,
        [
            {
                "key": "sales_category",
                "value": "fnb_cafe",
                "source": "derived",
                "evidence": long_text,
            }
        ],
        text=long_text,
    )
    evidence = result.update["draft"].fields[FieldKey.SALES_CATEGORY].evidence
    assert evidence is not None and len(evidence) <= 80


def test_a_user_correction_clears_evidence() -> None:
    master = load_master_data()
    draft, _w, _e = write_fields(
        new_inquiry_draft(),
        [("unit_type", "specialty", Source.DERIVED)],
        master=master,
        evidence={"unit_type": "coffee kiosk"},
    )
    assert draft.fields[FieldKey.UNIT_TYPE].evidence == "coffee kiosk"
    draft, _w, _e = write_fields(draft, [("unit_type", "store", Source.USER)], master=master)
    assert draft.fields[FieldKey.UNIT_TYPE].evidence is None


def test_evidence_is_kept_in_the_audit_trail() -> None:
    master = load_master_data()
    before = new_inquiry_draft()
    after, _w, _e = write_fields(
        before,
        [("unit_type", "specialty", Source.DERIVED), ("email", "a@b.example", Source.DERIVED)],
        master=master,
        evidence={"unit_type": "coffee kiosk", "email": "a@b.example"},
    )
    audit = AuditLog()
    record_draft_changes(audit, "s", before, after, actor="agent", via="agent")
    written = {e["payload"]["key"]: e["payload"] for e in audit.events("s")}
    assert written["unit_type"]["evidence"] == "coffee kiosk"
    assert "evidence" not in written["email"]  # personal fields are hashed, never quoted
