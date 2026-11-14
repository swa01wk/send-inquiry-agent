"""AGENT-DET (flow v2 test plan §4): every intake and call-centre scenario in
`docs/flow-v2/scenarios.json`, driven through the HTTP app with its scripted model.

The steps are the AGENT-LIVE catalogue runner's (`scripts/flow_v2_eval_live.py`), so the two
layers can't disagree about what a scenario is; here the model is the e2e script the
Playwright INT specs use (`tests/e2e_scripts/flow-v2-<id>.json`). Asserted per scenario:
every step ran, no invariant broke, each chart path holds, and the deterministic `expect`
rows. Wording checks stay with AGENT-LIVE.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from app.agent.case_graph import build_case_graph
from app.agent.graph import build_assisted_graph, build_graph
from app.agent.model import ScriptedChatModel
from app.agent.reviewer_graph import build_reviewer_graph
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from httpx import ASGITransport, AsyncClient

from tests.lifecycle.conftest import lifecycle_settings

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import eval_live  # noqa: E402
import flow_v2_eval_live as fv2  # noqa: E402

pytestmark = [
    pytest.mark.agent,
    pytest.mark.lease_admin,
    pytest.mark.cr_question,
    pytest.mark.approvals,
    pytest.mark.lead_approval,
    pytest.mark.intake_v2,
]

_CATALOGUE = json.loads(
    (Path(__file__).resolve().parents[3] / "docs" / "flow-v2" / "scenarios.json").read_text(
        encoding="utf-8"
    )
)
_IDS = [f"S{n}" for n in range(1, 18)] + ["CC1", "CC2", "CC3"]
_ENTRIES = {e["id"]: e for e in _CATALOGUE["scenarios"] if e["id"] in _IDS}


def script_name(scenario_id: str) -> str:
    return f"flow-v2-{scenario_id.lower()}"


@pytest.fixture
async def det(tmp_path: Path) -> AsyncIterator[tuple[AsyncClient, Any]]:
    settings = lifecycle_settings(tmp_path)

    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=[{"content": "OK"}] * 50)

    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=120)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    application.state.assisted_graph = build_assisted_graph(model_factory=factory)
    application.state.case_graph = build_case_graph(model_factory=factory)
    application.state.reviewer_graph = build_reviewer_graph(model_factory=factory)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, application


def _transcript(turns: list[Any]) -> str:
    lines = []
    for i, turn in enumerate(turns):
        cards = [d.get("card_type") for n, d in turn.events if n == "ui_card"]
        lines.append(f"  [{i}] {turn.user[:90]!r}\n      → {turn.assistant[:160]!r} cards={cards}")
    return "\n".join(lines)


@pytest.mark.parametrize("scenario_id", _IDS)
async def test_catalogue_scenario(det: tuple[AsyncClient, Any], scenario_id: str) -> None:
    client, app = det
    entry = _ENTRIES[scenario_id]
    scenario = eval_live.LiveScenario(
        name=f"{scenario_id} {entry['title']}",
        user_turns=[],
        evaluate=lambda _s, _t, _a: [],
        auto_otp=False,
        group="flow_v2",
        intake="v2",
        catalogue=entry,
    )
    outbox = await eval_live._fetch_outbox_messages(client)
    result, violations = await fv2.run_flow_v2_catalogue(
        client,
        app,
        scenario,
        outbox_messages=outbox,
        script=script_name(scenario_id),
        applicant_script=f"{script_name(scenario_id)}-applicant",
    )
    session = await app.state.session_store.get(result.session_id)
    path = await fv2._flow_path(client, result.session_id)
    checks: list[tuple[str, bool]] = [
        *[c for c in result.checks if c[0].startswith("all steps ran")],
        *fv2._flow_paths_ok(path, entry),
        *fv2._expect_checks(session, result.turns, app, entry, wording=False),
        *[(f"invariant {v.id} at step {n}: {v.detail}", False) for v, n in violations],
    ]
    failed = [name for name, ok in checks if not ok]
    assert not failed, (
        f"{scenario_id} failed: {failed}\n  path: {path}\n"
        f"  script step: {session.script_step if session else '?'}\n{_transcript(result.turns)}"
    )
