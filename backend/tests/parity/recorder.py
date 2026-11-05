"""Record parity scenarios through the HTTP app into normalised JSONL."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.config import Settings
from app.main import create_app
from app.services.container import build_services
from app.store.factory import make_session_store
from app.store.postgres import PostgresInquiryRepository
from httpx import ASGITransport, AsyncClient

from tests.parity.normalize import normalize_events
from tests.parity.scenarios import ParityScenario, ScriptStep, all_scenarios
from tests.scenarios.helpers import read_sse


async def _chat(
    client: AsyncClient,
    session_id: str,
    body: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    async with client.stream(
        "POST",
        f"/api/sessions/{session_id}/chat",
        json=body,
    ) as response:
        response.raise_for_status()
        return await read_sse(response)


async def _run_step(
    client: AsyncClient,
    app: Any,
    session_id: str,
    step: ScriptStep,
) -> list[tuple[str, dict[str, Any]]]:
    if step.kind == "message":
        assert step.text is not None
        return await _chat(client, session_id, {"type": "message", "text": step.text})
    if step.kind == "confirm_latest":
        session = await app.state.session_store.get(session_id)
        cards = [c for c in session.cards.values() if c.get("card_type") == "confirm_fields"]
        assert cards, "expected confirm_fields card before confirm_latest"
        card_id = str(cards[-1]["card_id"])
        return await _chat(
            client,
            session_id,
            {"type": "action", "action": "confirm_card", "payload": {"card_id": card_id}},
        )
    if step.kind == "action":
        assert step.action is not None
        return await _chat(
            client,
            session_id,
            {"type": "action", "action": step.action, "payload": step.payload},
        )
    if step.kind == "upload":
        assert step.doc_type and step.file_name
        response = await client.post(
            f"/api/sessions/{session_id}/documents",
            data={"doc_type": step.doc_type},
            files={"file": (step.file_name, step.content, "application/pdf")},
        )
        response.raise_for_status()
        body = response.json()
        return [
            ("ui_card", body["card"]),
            ("draft", body["draft"]),
        ]
    if step.kind == "verify_email":
        token = app.state.services.email_verification.demo_token(session_id)
        assert token
        return await _chat(
            client,
            session_id,
            {"type": "action", "action": "verify_email", "payload": {"token": token}},
        )
    if step.kind == "submit_otp":
        code = str(step.payload.get("code", "1234"))
        return await _chat(
            client,
            session_id,
            {"type": "action", "action": "submit_otp", "payload": {"code": code}},
        )
    msg = f"unknown script step kind: {step.kind}"
    raise ValueError(msg)


@asynccontextmanager
async def parity_client(
    settings: Settings,
    model_steps: list[dict[str, Any]],
) -> AsyncIterator[tuple[AsyncClient, Any]]:
    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=model_steps)

    cfg = settings.model_copy(update={"agent_mode": "scripted"})
    application = create_app(settings=cfg, model_factory=factory)
    application.state.settings = cfg
    session_store = make_session_store(cfg)
    if cfg.state_backend == "postgres":
        assert isinstance(session_store.inquiry_repo, PostgresInquiryRepository)
    application.state.session_store = session_store
    application.state.services = build_services(cfg)
    application.state.graph = build_graph(model_factory=factory)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http, application


async def record_scenario(
    settings: Settings,
    scenario: ParityScenario,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return normalised JSONL records and the create-session payload."""
    async with parity_client(settings, scenario.model_steps) as (client, app):
        created = await client.post(
            "/api/sessions",
            headers={"X-Test-Scenario": scenario.name},
        )
        created.raise_for_status()
        session_payload = created.json()
        session_id = str(session_payload["session_id"])

        raw_events: list[tuple[str, dict[str, Any]]] = []
        for step in scenario.script:
            turn = await _run_step(client, app, session_id, step)
            raw_events.extend(turn)

        return normalize_events(raw_events), session_payload


def golden_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "golden" / f"{name}.jsonl"


def write_golden(name: str, events: list[dict[str, Any]]) -> Path:
    path = golden_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item, ensure_ascii=False) for item in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def session_sidecar_path(name: str) -> Path:
    return golden_path(name).with_suffix(".session.json")


def write_session_snapshot(name: str, session_payload: dict[str, Any]) -> Path:
    from tests.parity.normalize import _walk

    path = session_sidecar_path(name)
    normalised = _walk(session_payload, {})
    path.write_text(json.dumps(normalised, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


async def record_all(settings: Settings) -> None:
    for scenario in all_scenarios():
        # Demo feedback §3.1: only re-record new CR-question goldens; older scripts keep
        # lookup behaviour via `X-Test-Scenario` and stay on disk until intentionally replaced.
        # GOLDEN_FORCE=1 re-records every golden (an intentional refresh).
        force = os.environ.get("GOLDEN_FORCE") == "1"
        if not force and scenario.name != "rd-cr-question" and golden_path(scenario.name).is_file():
            print(f"skip {scenario.name} (existing golden)")
            continue
        events, session_payload = await record_scenario(settings, scenario)
        write_golden(scenario.name, events)
        write_session_snapshot(scenario.name, session_payload)
        print(f"recorded {scenario.name}: {len(events)} events")
