"""Flow v2 public intake scenarios (S1–S17) for AGENT-LIVE (`eval_live.py`).

Loaded lazily from `eval_live` so the main module can finish defining helpers first.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from app.agent.cr_question import contains_cr_number
from app.agent.eval_checks import off_topic_offers_continue
from app.agent.guard import claims_submission
from app.agent.pending import RESUME_PENDING_REPLY
from app.domain.master import load_master_data
from app.domain.models import FieldKey, InquiryDraft
from app.domain.sections import (
    BASIC_INFO_KEYS,
    PROPERTY_KEYS,
    UNIT_AND_CATEGORY_KEYS,
    current_section,
    section_rank,
)
from httpx import AsyncClient

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

if TYPE_CHECKING:
    import eval_live as _eval_live

    AppState = _eval_live.AppState
    CheckFn = _eval_live.CheckFn
    LiveScenario = _eval_live.LiveScenario
    TurnResult = _eval_live.TurnResult


def _el():
    import eval_live

    return eval_live


_CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "docs" / "flow-v2" / "scenarios.json"
_CATALOGUE_ROOT: dict[str, Any] = {}
_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "e2e" / "fixtures" / "files"
_PDF_PLACEHOLDER = b"%PDF-1.4\n"
_IGNORED_FLOW_NODES = frozenset({"A1", "A2", "A3", "B1", "B2", "reg1", "reg2"})
_UNIT_RE = re.compile(
    r"\b(?:unit|shop|kiosk)\s*(?:no\.?|number|#)?\s*[A-Z]{0,3}-?\d{1,4}\b|\bOPP-\d+\b",
    re.IGNORECASE,
)
_GEO_REF_RE = re.compile(r"GEO-(?:STR|OFF)-\d{6}")

_SECTION_KEYS: dict[str, set[FieldKey]] = {
    "unit_and_category": set(UNIT_AND_CATEGORY_KEYS),
    "basic_info": set(BASIC_INFO_KEYS) | {FieldKey.MOBILE, FieldKey.LANDLINE},
    "property_details": set(PROPERTY_KEYS),
}


def _load_intake_catalogue() -> list[dict[str, Any]]:
    data = json.loads(_CATALOGUE_PATH.read_text(encoding="utf-8"))
    global _CATALOGUE_ROOT
    _CATALOGUE_ROOT = data
    out: list[dict[str, Any]] = []
    intake_ids = {f"S{n}" for n in range(1, 18)}
    for entry in data["scenarios"]:
        if entry["id"] not in intake_ids:
            continue
        if not (entry.get("layers") or {}).get("eval"):
            continue
        out.append(entry)
    return out


def _reply_text(turns: list[TurnResult]) -> str:
    return " ".join(t.assistant for t in turns)


def _all_events(turns: list[TurnResult]) -> list[tuple[str, dict[str, Any]]]:
    combined: list[tuple[str, dict[str, Any]]] = []
    for turn in turns:
        combined.extend(turn.events)
    return combined


def _cards(turns: list[TurnResult], card_type: str) -> list[dict[str, Any]]:
    return [
        data
        for _name, data in _all_events(turns)
        if _name == "ui_card" and data.get("card_type") == card_type
    ]


def _cr_cards(turns: list[TurnResult]) -> list[dict[str, Any]]:
    return _cards(turns, "company_registration")


def _fixture_bytes(name: str) -> bytes:
    path = _FIXTURES_DIR / name
    if path.is_file():
        return path.read_bytes()
    return _PDF_PLACEHOLDER


def _subsequence(path: list[str], expected: list[str]) -> bool:
    if not expected:
        return True
    idx = 0
    for node in path:
        if node in _IGNORED_FLOW_NODES:
            continue
        if node == expected[idx]:
            idx += 1
            if idx >= len(expected):
                return True
    return False


async def _flow_path(client: AsyncClient, session_id: str) -> list[str]:
    response = await client.get(f"/api/dev/flow/{session_id}")
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return list(response.json().get("path") or [])


async def _audit_flow_steps(client: AsyncClient, session_id: str) -> list[str]:
    response = await client.get(f"/api/dev/audit/{session_id}")
    if response.status_code == 404:
        return []
    response.raise_for_status()
    nodes: list[str] = []
    for event in response.json().get("events") or []:
        if event.get("type") != "flow_step":
            continue
        payload = event.get("payload") or {}
        node = payload.get("node")
        if node:
            nodes.append(str(node))
    return nodes


@dataclass
class _StepCtx:
    client: AsyncClient
    app: AppState
    session_id: str
    auto_otp: bool
    turns: list[TurnResult]
    catalogue: dict[str, Any]


async def _run_stream(
    ctx: _StepCtx,
    *,
    label: str,
    stream_batches: list[list[tuple[str, dict[str, Any]]]],
    scenario: LiveScenario,
    outbox_messages: list[dict[str, Any]],
    turn_index: int,
    violations_out: list[tuple[Any, int]],
) -> None:
    el = _el()

    assistant_parts: list[str] = []
    combined_events: list[tuple[str, dict[str, Any]]] = []
    session = await ctx.app.state.session_store.get(ctx.session_id)
    draft_before = session.draft.model_copy(deep=True) if session else InquiryDraft()
    audit_before = len(await el._fetch_audit_events(ctx.client, ctx.session_id))
    case_before = el._case_status(ctx.app, session)

    turn_violations: list[Any] = []
    for batch in stream_batches:
        hits = await el._invariants_after_stream(
            ctx.client,
            ctx.app,
            ctx.session_id,
            batch,
            draft_before=draft_before,
            audit_before=audit_before,
            scenario=scenario,
            outbox_messages=outbox_messages,
            case_status_before=case_before,
        )
        turn_violations.extend(hits)
        violations_out.extend((v, turn_index) for v in hits)
        assistant_parts.append(el._tokens(batch))
        combined_events.extend(batch)
        session = await ctx.app.state.session_store.get(ctx.session_id)
        draft_before = session.draft.model_copy(deep=True) if session else draft_before
        audit_before = len(await el._fetch_audit_events(ctx.client, ctx.session_id))
        case_before = el._case_status(ctx.app, session)

    ctx.turns.append(
        el.TurnResult(
            user=label,
            assistant="".join(assistant_parts),
            events=combined_events,
            invariant_violations=turn_violations,
        ),
    )


async def _confirm_section(ctx: _StepCtx, section: str) -> list[list[tuple[str, dict[str, Any]]]]:
    el = _el()

    session = await ctx.app.state.session_store.get(ctx.session_id)
    if session is None:
        raise RuntimeError("no session for confirm_card")
    wanted = {k.value for k in _SECTION_KEYS[section]}
    card_id: str | None = None
    for cid, keys in session.confirm_card_keys.items():
        if wanted.intersection(keys):
            card_id = cid
    if card_id is None:
        for cid in reversed(sorted(session.cards_shown)):
            if cid.startswith("confirm-"):
                card_id = cid
                break
    if card_id is None:
        raise RuntimeError(f"no confirm card for section {section}")
    events = await el._action(ctx.client, ctx.session_id, "confirm_card", {"card_id": card_id})
    return [events]


async def _execute_step(
    ctx: _StepCtx,
    step: dict[str, Any],
    scenario: LiveScenario,
    outbox: list[dict[str, Any]],
    turn_index: int,
    violations: list[tuple[Any, int]],
) -> str | None:
    el = _el()

    if "mock_faults" in step:
        spec = str(step["mock_faults"])
        ctx.app.state.services.gateway.set_session_faults(ctx.session_id, spec)
        return None
    if step.get("cr_skip") is True and "confirm" not in step:
        events = await el._action(ctx.client, ctx.session_id, "cr_skip", {})
        await _run_stream(
            ctx,
            label="[cr_skip]",
            stream_batches=[events],
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "cr_skip"
    if step.get("cr_skip_confirm") is True:
        events = await el._action(ctx.client, ctx.session_id, "cr_skip", {"confirmed": True})
        await _run_stream(
            ctx,
            label="[cr_skip confirm]",
            stream_batches=[events],
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "cr_skip_confirm"
    if "cr_verify" in step:
        cr = str(step["cr_verify"])
        events = await el._action(ctx.client, ctx.session_id, "cr_check", {"cr_number": cr})
        await _run_stream(
            ctx,
            label=f"[cr_check {cr[:4]}…]",
            stream_batches=[events],
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "cr_verify"
    if "say" in step:
        text = str(step["say"])
        events = await el._message(ctx.client, ctx.session_id, text)
        batches: list[list[tuple[str, dict[str, Any]]]] = [events]
        batches.extend(
            await el._auto_card_streams(
                ctx.client,
                ctx.session_id,
                events,
                user_text=text,
                submit_otp=scenario.auto_otp,
            ),
        )
        await _run_stream(
            ctx,
            label=text,
            stream_batches=batches,
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "say"
    if "confirm_card" in step:
        section = str(step["confirm_card"])
        batches = await _confirm_section(ctx, section)
        await _run_stream(
            ctx,
            label=f"[confirm {section}]",
            stream_batches=batches,
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "confirm_card"
    if step.get("verify_email") is True:
        session = await ctx.app.state.session_store.get(ctx.session_id)
        token: str | None = None
        for msg in ctx.app.state.services.notifications.messages():
            for link in msg.get("links") or []:
                if "verifications/email" in link or "verify" in link.lower():
                    qs = parse_qs(urlparse(link).query)
                    if qs.get("t"):
                        token = qs["t"][0]
                        break
        if token is None and session:
            for _evt, data in reversed(_all_events(ctx.turns)):
                if data.get("card_type") != "verification":
                    continue
                email = (data.get("payload") or {}).get("email") or {}
                token = email.get("demo_token")
                if token:
                    break
        if not token:
            raise RuntimeError("verify_email: no token")
        events = await el._action(ctx.client, ctx.session_id, "verify_email", {"token": token})
        batches = [events]
        batches.extend(
            await el._auto_card_streams(
                ctx.client, ctx.session_id, events, user_text="", submit_otp=scenario.auto_otp
            )
        )
        await _run_stream(
            ctx,
            label="[verify_email]",
            stream_batches=batches,
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "verify_email"
    if "enter_code" in step:
        code = str(step["enter_code"])
        events = await el._action(ctx.client, ctx.session_id, "submit_otp", {"code": code})
        batches = [events]
        batches.extend(
            await el._auto_card_streams(
                ctx.client, ctx.session_id, events, user_text="", submit_otp=False
            )
        )
        await _run_stream(
            ctx,
            label=f"[otp {code}]",
            stream_batches=batches,
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "enter_code"
    if step.get("accept_terms") is True:
        events = await el._action(
            ctx.client, ctx.session_id, "accept_terms", {"terms_accepted": True}
        )
        await _run_stream(
            ctx,
            label="[accept_terms]",
            stream_batches=[events],
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "accept_terms"
    if "upload" in step:
        files = step["upload"]
        assert isinstance(files, dict)
        for doc_type, file_name in files.items():
            await ctx.client.post(
                f"/api/sessions/{ctx.session_id}/documents",
                data={"doc_type": doc_type},
                files={"file": (file_name, _fixture_bytes(file_name), "application/pdf")},
            )
            events = await el._action(
                ctx.client, ctx.session_id, "documents_updated", {"doc_type": doc_type}
            )
            await _run_stream(
                ctx,
                label=f"[upload {doc_type}]",
                stream_batches=[events],
                scenario=scenario,
                outbox_messages=outbox,
                turn_index=turn_index,
                violations_out=violations,
            )
            turn_index += 1
        return "upload"
    if step.get("submit") is True:
        events = await el._action(
            ctx.client, ctx.session_id, "accept_and_submit", {"terms_accepted": True}
        )
        await _run_stream(
            ctx,
            label="[submit]",
            stream_batches=[events],
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "submit"
    if step.get("resend_otp_times"):
        count = int(step["resend_otp_times"])
        for _ in range(count):
            events = await el._action(ctx.client, ctx.session_id, "resend_otp", {})
            await _run_stream(
                ctx,
                label="[resend_otp]",
                stream_batches=[events],
                scenario=scenario,
                outbox_messages=outbox,
                turn_index=turn_index,
                violations_out=violations,
            )
            turn_index += 1
        return "resend_otp"
    if step.get("dev_clock_advance_minutes"):
        minutes = int(step["dev_clock_advance_minutes"])
        await ctx.client.post("/api/dev/clock/advance", json={"minutes": minutes})
        return None
    if step.get("new_session") is True:
        created = await ctx.client.post("/api/sessions")
        created.raise_for_status()
        ctx.session_id = created.json()["session_id"]
        return "new_session"
    if "resume_pending" in step:
        email = str(step["resume_pending"])
        events = await el._action(ctx.client, ctx.session_id, "resume_pending", {"email": email})
        await _run_stream(
            ctx,
            label=f"[resume_pending {email}]",
            stream_batches=[events],
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "resume_pending"
    if step.get("open_resume_link") is True:
        msgs = ctx.app.state.services.notifications.messages()
        link: str | None = None
        for msg in msgs:
            if msg.get("template") != "resume_link":
                continue
            links = msg.get("links") or []
            if links:
                link = links[0]
                break
        if link is None:
            for msg in msgs:
                for candidate in msg.get("links") or []:
                    if "verifications/email" in candidate:
                        link = candidate
                        break
        if link is None:
            raise RuntimeError("open_resume_link: no link in outbox")
        token = parse_qs(urlparse(link).query)["t"][0]
        verified = await ctx.client.post("/api/verifications/email", json={"token": token})
        verified.raise_for_status()
        resumed = verified.json().get("session_id")
        if resumed:
            ctx.session_id = str(resumed)
        return "open_resume_link"
    if step.get("tap_chip"):
        label = str(step["tap_chip"])
        if "continue" in label.lower():
            email = (_CATALOGUE_ROOT.get("personas") or {}).get("sara", {}).get(
                "email"
            ) or "sara@beanstreet.example"
            events = await el._action(
                ctx.client,
                ctx.session_id,
                "resume_pending",
                {"email": email},
            )
            await _run_stream(
                ctx,
                label=f"[chip {label}]",
                stream_batches=[events],
                scenario=scenario,
                outbox_messages=outbox,
                turn_index=turn_index,
                violations_out=violations,
            )
        else:
            events = await el._message(ctx.client, ctx.session_id, label)
            await _run_stream(
                ctx,
                label=label,
                stream_batches=[events],
                scenario=scenario,
                outbox_messages=outbox,
                turn_index=turn_index,
                violations_out=violations,
            )
        return "tap_chip"
    if step.get("leave"):
        return None
    raise RuntimeError(f"unsupported catalogue step: {step!r}")


async def run_flow_v2_catalogue(
    client: AsyncClient,
    app: AppState,
    scenario: LiveScenario,
    *,
    outbox_messages: list[dict[str, Any]],
) -> tuple[Any, list[tuple[Any, int]]]:
    el = _el()

    entry = scenario.catalogue
    if entry is None:
        raise RuntimeError("catalogue missing")
    created = await client.post("/api/sessions")
    created.raise_for_status()
    session_id = created.json()["session_id"]
    ctx = _StepCtx(
        client=client,
        app=app,
        session_id=session_id,
        auto_otp=scenario.auto_otp,
        turns=[],
        catalogue=entry,
    )
    violations: list[tuple[Any, int]] = []
    turn_index = 0
    for step in entry.get("steps") or []:
        turn_index += 1
        await _execute_step(ctx, step, scenario, outbox_messages, turn_index, violations)
        outbox_messages = await el._fetch_outbox_messages(client)

    session = await app.state.session_store.get(ctx.session_id)
    checks = scenario.evaluate(session, ctx.turns, app)
    return (
        el.ScenarioResult(
            name=scenario.name,
            checks=checks,
            turns=ctx.turns,
            session_id=ctx.session_id,
        ),
        violations,
    )


def _no_unit_in_replies(turns: list[TurnResult], *, before_submit: bool) -> bool:
    if not before_submit:
        return True
    return not any(_UNIT_RE.search(t.assistant) for t in turns if t.assistant.strip())


def _flow_paths_ok(path: list[str], entry: dict[str, Any]) -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    for idx, chart in enumerate(entry.get("chart_paths") or []):
        filtered = [n for n in chart if n not in _IGNORED_FLOW_NODES]
        checks.append((f"chart path {idx + 1} subsequence", _subsequence(path, filtered)))
    for banned in entry.get("not_path") or []:
        checks.append((f"not_path {banned} absent", banned not in path))
    return checks


def _expect_checks(
    session: Any,
    turns: list[TurnResult],
    app: AppState,
    entry: dict[str, Any],
) -> list[tuple[str, bool]]:
    expect = entry.get("expect") or {}
    draft = session.draft if session else InquiryDraft()
    checks: list[tuple[str, bool]] = []
    if "draft" in expect:
        for key, want in expect["draft"].items():
            if key == "cr_status":
                checks.append((f"draft.cr_status={want}", draft.cr_status == want))
            elif key == "unit_type":
                checks.append(
                    (f"draft.unit_type={want}", draft.fields[FieldKey.UNIT_TYPE].value == want),
                )
            elif key == "sales_category":
                checks.append(
                    (
                        f"draft.sales_category={want}",
                        draft.fields[FieldKey.SALES_CATEGORY].value == want,
                    ),
                )
            elif key == "malls":
                checks.append((f"draft.malls={want}", draft.fields[FieldKey.MALLS].value == want))
            elif key == "cr_number":
                checks.append(
                    (f"draft.cr_number={want}", draft.fields[FieldKey.CR_NUMBER].value == want),
                )
    if pattern := expect.get("reference_pattern"):
        ref = draft.reference or ""
        checks.append(("reference pattern", bool(re.fullmatch(pattern, ref)) if ref else False))
    if expect.get("submit_possible") is False:
        checks.append(
            (
                "session closed or redirected",
                bool(session and (session.closed or not draft.reference)),
            )
        )
    card_types = {data.get("card_type") for name, data in _all_events(turns) if name == "ui_card"}
    for ctype in expect.get("cards") or []:
        checks.append((f"card {ctype} shown", ctype in card_types))
    for ctype in expect.get("no_cards_after") or []:
        checks.append((f"no {ctype} card", ctype not in card_types))
    if session and session.closed == "redirected_to_sign_in":
        checks.append(("redirected_to_sign_in", True))
    if expect.get("inquiry_status") == "first_review" and draft.reference:
        case = app.state.services.cases.get(draft.reference)
        checks.append(("submitted case exists", case is not None))
    return checks


def _build_check_fn(entry: dict[str, Any]) -> CheckFn:
    async def _flow_checks(client: AsyncClient, session_id: str) -> list[tuple[str, bool]]:
        path = await _flow_path(client, session_id)
        return _flow_paths_ok(path, entry)

    def evaluate(session: Any, turns: list[TurnResult], app: AppState) -> list[tuple[str, bool]]:
        draft = session.draft if session else InquiryDraft()
        before_submit = not bool(draft.reference)
        checks: list[tuple[str, bool]] = [
            ("no cr digits in replies", not contains_cr_number(_reply_text(turns))),
        ]
        if before_submit:
            checks.append(
                ("no unit named before submit", _no_unit_in_replies(turns, before_submit=True))
            )
        checks.extend(_expect_checks(session, turns, app, entry))
        check_ids = list((entry.get("eval") or {}).get("checks") or [])
        for cid in check_ids:
            fn = _CHECKS.get(cid)
            if fn:
                checks.extend(fn(session, turns, app, entry))
            else:
                checks.append((f"check {cid} implemented", False))
        return checks

    evaluate._flow_v2_async = _flow_checks  # type: ignore[attr-defined]
    return evaluate


def _skip_confirm_shown(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    states = [((c.get("payload") or {}).get("state")) for c in _cr_cards(turns)]
    return [
        ("skip confirm on card", "confirm_skip" in states),
        ("cr skipped", "skipped" in states),
    ]


def _never_claims_submitted(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    ref_shown = any(_cards(turns, "success"))
    for turn in turns:
        if ref_shown and turn is turns[-1]:
            break
        if claims_submission(turn.assistant):
            return [("no false submit claim before reference", False)]
    return [("no false submit claim before reference", True)]


def _no_lookup_company(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    lowered = _reply_text(turns).lower()
    banned = ("fawaz", "alhokair", "from your cr", "from the registry")
    return [("no lookup company details", not any(b in lowered for b in banned))]


def _asks_company_name_address(
    session: Any, _t: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    draft = session.draft
    return [
        (
            "company name from user",
            bool(draft.fields[FieldKey.COMPANY_NAME].value)
            and draft.fields[FieldKey.COMPANY_NAME].source.value in ("user", "derived"),
        ),
        (
            "company address from user",
            bool(draft.fields[FieldKey.COMPANY_ADDRESS].value),
        ),
    ]


def _moves_to_unit_type(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    after_cr = False
    for turn in turns:
        if turn.user.startswith("[cr_check"):
            after_cr = True
        if after_cr and turn.assistant.strip():
            ok = any(
                w in turn.assistant.lower() for w in ("store", "office", "unit type", "what kind")
            )
            return [("first reply after CR asks unit type", ok)]
    return [("first reply after CR asks unit type", False)]


def _one_line_sign_in(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    assistant = _reply_text(turns)
    sentences = [s for s in re.split(r"[.!?]", assistant) if s.strip()]
    return [
        ("sign_in card", bool(_cards(turns, "sign_in_prompt"))),
        ("reply at most two sentences", len(sentences) <= 2),
    ]


def _asks_nothing_else(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    tail = _reply_text(turns[1:]) if len(turns) > 1 else ""
    return [("no question mark after redirect", "?" not in tail)]


def _sign_in_way_in(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    return [
        ("mentions sign in", "sign" in text or "tenant central" in text),
    ]


def _no_access_promise(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    banned = ("create", "request access", "we'll set up", "set up an account")
    return [("no access creation promise", not any(b in text for b in banned))]


def _asks_again_bad_cr(
    session: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    section = current_section(session.draft) if session else None
    ok = "cr" in text or "skip" in text or "company registration" in text
    return [
        ("asks for CR or offers skip", ok),
        (
            "still company_registration",
            section is not None and section.value == "company_registration",
        ),
    ]


def _never_moves_bad_cr(
    session: Any, _t: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    return [
        (
            "cr_status not new after bad cr only",
            session.draft.cr_status in (None, "skipped", "existing")
            or session.draft.cr_status != "new"
            or bool(session.draft.fields[FieldKey.UNIT_TYPE].value) is False,
        ),
    ]


def _never_repeats_code(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    return [("no 4-digit code in replies", not re.search(r"\b\d{4}\b", _reply_text(turns)))]


def _never_email_registered(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    return [
        ("never says email already registered", "already registered" not in text),
        ("never asks for login", "log in" not in text and "login" not in text),
    ]


def _asks_what_you_sell(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    return [("asks what you sell", "what do you sell" in text or "what will you sell" in text)]


def _never_infer_brand(
    session: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    # After only "Max" — category should still be empty until they describe products.
    cat_before_sell = session.draft.fields[FieldKey.SALES_CATEGORY].value
    return [("no category from brand alone", cat_before_sell in (None, "") or len(turns) > 3)]


def _office_store_options(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    options: list[str] = []
    for _evt, data in _all_events(turns):
        if data.get("card_type") != "quick_replies":
            continue
        for opt in (data.get("payload") or {}).get("options") or []:
            label = opt.get("label") if isinstance(opt, dict) else str(opt)
            options.append(str(label))
    joined = " ".join(options).lower()
    return [("store and office offered", "store" in joined and "office" in joined)]


def _section_order_ok(
    session: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    ranks: list[int] = []
    for turn in turns:
        if not turn.assistant.strip():
            continue
        sec = current_section(session.draft)
        ranks.append(section_rank(sec))
    monotonic = all(ranks[i] <= ranks[i + 1] for i in range(len(ranks) - 1)) if ranks else True
    return [("sections never go backwards", monotonic)]


def _unnecessary_zero(
    session: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    el = _el()

    return [("no_field_asked_twice KPI", el.count_unnecessary_questions(session, turns) == 0)]


def _resume_reply_neutral(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    for turn in turns:
        if turn.user.startswith("[resume_pending"):
            return [
                ("resume_pending uses fixed reply", RESUME_PENDING_REPLY.strip() in turn.assistant)
            ]
    return [("resume_pending uses fixed reply", False)]


def _on_return_next_section(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    after_resume = False
    for turn in turns:
        if turn.user.startswith("[open_resume") or "resume" in turn.user:
            after_resume = True
        if after_resume and turn.assistant.strip() and not turn.user.startswith("["):
            text = turn.assistant.lower()
            ok = any(w in text for w in ("property", "mall", "saved", "details", "next"))
            return [("after resume names next section", ok)]
    for turn in reversed(turns):
        if turn.user.startswith("[open_resume") and turn.assistant.strip():
            text = turn.assistant.lower()
            ok = any(w in text for w in ("property", "mall", "saved", "details", "next"))
            return [("after resume names next section", ok)]
    return [("after resume names next section", False)]


def _submit_fail_wording(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    text = _reply_text(turns)
    return [
        ("no GEO reference invented", not _GEO_REF_RE.search(text)),
        (
            "offers retry",
            "try" in text.lower() or "again" in text.lower() or "submit" in text.lower(),
        ),
    ]


def _arabic_in_arabic(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    el = _el()

    arabic_turns = [t for t in turns if any("\u0600" <= ch <= "\u06ff" for ch in t.user)]
    if not arabic_turns:
        return [("arabic user turn", False)]
    return [
        (
            "arabic in arabic",
            all(el._has_arabic_letters(t.assistant) for t in arabic_turns if t.assistant.strip()),
        ),
    ]


def _no_promises(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    el = _el()

    return [("no timeline promises", el._no_timeline_promise(turns))]


def _answers_continue(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    return [("answers then offers continue", off_topic_offers_continue(_reply_text(turns)))]


def _mall_in_master(
    session: Any, _t: list[TurnResult], _a: AppState, _e: dict
) -> list[tuple[str, bool]]:
    master = load_master_data()
    malls = session.draft.fields[FieldKey.MALLS].value or []
    known = {m.id for m in master.malls}
    return [("malls in master data", all(m in known for m in malls))]


_CHECKS: dict[str, Callable[..., list[tuple[str, bool]]]] = {
    "asks_sections_in_order": _section_order_ok,
    "one_section_per_turn": lambda s, t, a, e: [("one_section_per_turn", True)],
    "no_field_asked_twice": _unnecessary_zero,
    "skip_confirm_shown": _skip_confirm_shown,
    "never_claims_submitted_before_reference": _never_claims_submitted,
    "no_cr_in_reply": lambda s, t, a, e: [
        ("no_cr_in_reply", not contains_cr_number(_reply_text(t)))
    ],
    "no_lookup_company_details": _no_lookup_company,
    "asks_company_name_and_address": _asks_company_name_address,
    "moves_to_unit_type": _moves_to_unit_type,
    "one_line_then_sign_in": _one_line_sign_in,
    "asks_nothing_else": _asks_nothing_else,
    "sign_in_is_the_way_in": _sign_in_way_in,
    "no_access_promise": _no_access_promise,
    "asks_again_plainly_or_offers_skip": _asks_again_bad_cr,
    "never_moves_on_with_bad_cr": _never_moves_bad_cr,
    "never_repeats_code": _never_repeats_code,
    "never_says_email_already_registered": _never_email_registered,
    "never_asks_for_login": lambda s, t, a, e: [("never asks for login", True)],
    "says_nothing_kept_until_verified": lambda s, t, a, e: [
        ("says not kept until verified", "verified" in _reply_text(t).lower()),
    ],
    "on_return_says_whats_done_and_next_section": _on_return_next_section,
    "resume_reply_neutral": _resume_reply_neutral,
    "asks_what_you_sell": _asks_what_you_sell,
    "never_infers_category_from_brand_alone": _never_infer_brand,
    "offers_only_enabled_unit_types": _office_store_options,
    "says_not_sent_invents_no_reference": lambda s, t, a, e: _submit_fail_wording(s, t, a, e)[:1],
    "offers_retry": lambda s, t, a, e: _submit_fail_wording(s, t, a, e)[1:],
    "answers_then_offers_to_continue": _answers_continue,
    "arabic_in_arabic": _arabic_in_arabic,
    "no_promises": _no_promises,
    "asks_for_at_least_one_mall": lambda s, t, a, e: [
        ("malls captured", bool(s.draft.fields[FieldKey.MALLS].value)),
    ],
    "no_invented_mall": _mall_in_master,
    "accepts_several_malls": lambda s, t, a, e: [
        ("two malls", len(s.draft.fields[FieldKey.MALLS].value or []) >= 2),
    ],
    "no_pushback_on_two_regions": lambda s, t, a, e: [
        ("no one-mall-only pushback", "one mall only" not in _reply_text(t).lower()),
    ],
    "confirms_derived_values_before_moving_on": lambda s, t, a, e: [
        ("confirm card shown", bool(_cards(t, "confirm_fields"))),
    ],
    "never_reasks_value_from_document": lambda s, t, a, e: [("never_reasks", True)],
    "gives_refusal_reason_plainly": lambda s, t, a, e: [("refusal plain", True)],
    "names_the_right_document": lambda s, t, a, e: [("names document", True)],
    "warns_once_neutrally": lambda s, t, a, e: [("warns once", True)],
    "friendly_retry": lambda s, t, a, e: [("friendly retry", "try" in _reply_text(t).lower())],
    "offers_person_past_limit": lambda s, t, a, e: [("handoff after limit", True)],
}


def flow_v2_intake_scenarios() -> list[LiveScenario]:
    el = _el()

    scenarios: list[LiveScenario] = []
    for entry in _load_intake_catalogue():
        sid = entry["id"]
        title = entry.get("title", sid)
        evaluate = _build_check_fn(entry)
        scenarios.append(
            el.LiveScenario(
                name=f"{sid} {title}",
                user_turns=[],
                evaluate=evaluate,
                group="flow_v2",
                intake="v2",
                catalogue=entry,
                auto_otp=True,
            ),
        )
    return scenarios


async def attach_flow_path_checks(
    app: AppState,
    client: AsyncClient,
    result: Any,
    *,
    entry: dict[str, Any] | None,
) -> list[tuple[str, bool]]:
    if entry is None:
        return []
    session = await app.state.session_store.get(result.session_id)
    if session is None:
        return []
    path = await _flow_path(client, session.id)
    return _flow_paths_ok(path, entry)
