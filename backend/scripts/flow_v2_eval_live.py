"""Flow v2 catalogue scenarios for AGENT-LIVE (`eval_live.py`): the public intake (S1–S17)
and the call-centre stories (CC1–CC3).

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
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
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


def _el() -> Any:
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
    intake_ids = {f"S{n}" for n in range(1, 18)} | {"CC1", "CC2", "CC3"}
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
    # CC1–CC3: the executive's chat; `session_id` moves to the applicant's after the link.
    staff_session_id: str | None = None


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
    draft_before = session.draft.model_copy(deep=True) if session else new_inquiry_draft()
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
    """Confirm what is still unconfirmed in a section, the way a person would.

    Values the user typed are saved confirmed, so there is often nothing to confirm: then
    this step does nothing. Otherwise tap Confirm on the card that shows them, or say yes
    in chat when no card covers them (the model then calls `confirm_fields`).
    """
    el = _el()

    session = await ctx.app.state.session_store.get(ctx.session_id)
    if session is None:
        raise RuntimeError("no session for confirm_card")
    open_keys: set[str] = set()
    for key in _SECTION_KEYS[section]:
        field_value = session.draft.fields[key]
        if field_value.value not in (None, "", []) and not field_value.confirmed:
            open_keys.add(key.value)
    if not open_keys:
        return []
    batches: list[list[tuple[str, dict[str, Any]]]] = []
    # Every card that still shows an open value (a profile upload makes one per document).
    for cid, keys in reversed(list(session.confirm_card_keys.items())):
        if open_keys.intersection(keys):
            batches.append(
                await el._action(ctx.client, ctx.session_id, "confirm_card", {"card_id": cid})
            )
            open_keys -= set(keys)
    if open_keys:
        batches.append(await el._message(ctx.client, ctx.session_id, "Yes, that's all correct."))
    return batches


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
        if not batches:
            return None
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
        if session is None:
            raise RuntimeError("verify_email: no session")
        if session.draft.email_verified:
            return None
        token: str | None = None
        # This session's newest verification card first, then its email in the outbox.
        for _evt, data in reversed(_all_events(ctx.turns)):
            if data.get("card_type") != "verification":
                continue
            email = (data.get("payload") or {}).get("email") or {}
            token = email.get("demo_token")
            if token:
                break
        address = str(session.draft.fields[FieldKey.EMAIL].value or "")
        if token is None and address:
            for msg in reversed(ctx.app.state.services.notifications.messages(to=address)):
                if msg.get("template") != "email_verification_link":
                    continue
                for verify_link in msg.get("links") or []:
                    qs = parse_qs(urlparse(verify_link).query)
                    if qs.get("t"):
                        token = qs["t"][0]
                        break
                if token:
                    break
        if not token:
            raise RuntimeError(
                "verify_email: no verification link; the agent never called send_verification"
            )
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
        await _proceed_basic_info_once(ctx, scenario, outbox, turn_index, violations)
        session = await ctx.app.state.session_store.get(ctx.session_id)
        if session is not None and session.draft.mobile_verified:
            return None
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
        await ctx.client.post("/api/dev/clock/advance", json={"hours": minutes / 60})
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
    if "pick_malls" in step:
        master = load_master_data()
        names = [str(n).strip().lower() for n in step["pick_malls"]]
        mall_ids = [m.id for m in master.malls if m.name.strip().lower() in names]
        if len(mall_ids) != len(names):
            raise RuntimeError(f"pick_malls: unknown mall in {step['pick_malls']!r}")
        events = await el._action(
            ctx.client, ctx.session_id, "select_malls", {"mall_ids": mall_ids}
        )
        await _run_stream(
            ctx,
            label=f"[pick_malls {', '.join(mall_ids)}]",
            stream_batches=[events],
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )
        return "pick_malls"
    if step.get("reviewer") == "approve_documents_and_first_level":
        session = await ctx.app.state.session_store.get(ctx.session_id)
        reference = session.draft.reference if session else None
        if not reference:
            raise RuntimeError("reviewer: the inquiry was never submitted")
        await el._approve_intake_documents(ctx.client, reference)
        reviewer_id = await el._reviewer_who_can(ctx.client, reference, "approve_first")
        response = await ctx.client.post(
            f"/api/review/cases/{reference}/actions",
            json={"action": "approve_first", "payload": {}},
            headers={"X-Reviewer-Id": reviewer_id},
        )
        response.raise_for_status()
        return "reviewer"
    if "seed_open_inquiry" in step:
        await _seed_open_inquiry(ctx, dict(step["seed_open_inquiry"]))
        return None
    if cc_kind := next((k for k in _CC_STEPS if k in step), None):
        return await _execute_cc_step(
            ctx, cc_kind, step[cc_kind], scenario, outbox, turn_index, violations
        )
    if step.get("leave"):
        return None
    raise RuntimeError(f"unsupported catalogue step: {step!r}")


async def _seed_open_inquiry(ctx: _StepCtx, spec: dict[str, Any]) -> str:
    """An inquiry already submitted for this CR and mall (S15), in its own session."""
    el = _el()
    from app.domain.draft_ops import write_fields
    from app.domain.models import Source

    master = load_master_data()
    created = await ctx.client.post("/api/sessions")
    created.raise_for_status()
    seed_id = created.json()["session_id"]
    seeded = await ctx.app.state.session_store.get(seed_id)
    draft = el._ready_to_submit_draft(ctx.app)
    draft, _, errors = write_fields(
        draft,
        [
            (FieldKey.CR_NUMBER.value, str(spec["cr_number"]), Source.USER),
            (FieldKey.MALLS.value, [str(spec["mall"])], Source.USER),
        ],
        master=master,
    )
    if errors:
        raise RuntimeError(f"seed_open_inquiry: {errors}")
    draft.cr_status = "new"
    draft.intake_flow = seeded.draft.intake_flow
    draft.terms_accepted = True
    seeded.draft = draft
    await ctx.app.state.session_store.save(seeded)
    events = await el._action(ctx.client, seed_id, "accept_and_submit", {"terms_accepted": True})
    success = _cards([el.TurnResult(user="", assistant="", events=events)], "success")
    if not success:
        raise RuntimeError("seed_open_inquiry: submit failed")
    return str(success[0]["payload"]["reference"])


_STAFF_HEADERS = {"X-Staff-Id": "customer-care-1"}
STAFF_LABEL = "[staff] "

# CC1–CC3: what the executive dictates for each section (the caller's words, relayed).
_CC_DICTATION: dict[str, dict[str, str]] = {
    "CC2": {
        "unit_and_category": "They want a store. They sell specialty coffee and pastries.",
        "basic_info": (
            "Company is Oasis Coffee Company, King Fahd Road, Riyadh. The brand is Oasis "
            "Coffee. The caller is Huda Saleh, mobile 0507654321."
        ),
        "property_details": (
            "Riyadh Mall A, 40 to 80 square metres, budget 150,000 to 250,000 riyals a year."
        ),
    },
    "CC3": {
        "unit_and_category": "A store — they sell specialty coffee and pastries.",
        "basic_info": (
            "The brand is Bean Street. The caller is Sara Ali, sara@beanstreet.example, "
            "mobile 0501234567."
        ),
        "property_details": (
            "Riyadh Mall A, 40 to 80 square metres, budget 150,000 to 250,000 riyals a year."
        ),
    },
}

_CC_STEPS = (
    "cc_cr",
    "cc_contact_check",
    "cc_send_sign_in_link",
    "cc_capture",
    "cc_submit",
    "open_application_link",
    "edit_field",
)

_FIELD_WORDS = {"last_name": "last name", "first_name": "first name", "mobile": "mobile"}


async def _execute_cc_step(
    ctx: _StepCtx,
    kind: str,
    arg: Any,
    scenario: LiveScenario,
    outbox: list[dict[str, Any]],
    turn_index: int,
    violations: list[tuple[Any, int]],
) -> str:
    el = _el()

    async def run(label: str, batches: list[list[tuple[str, dict[str, Any]]]]) -> None:
        await _run_stream(
            ctx,
            label=label,
            stream_batches=batches,
            scenario=scenario,
            outbox_messages=outbox,
            turn_index=turn_index,
            violations_out=violations,
        )

    if kind == "cc_cr":
        text = f"The caller's CR number is {arg}."
        await run(STAFF_LABEL + text, [await el._message(ctx.client, ctx.session_id, text)])
    elif kind == "cc_contact_check":
        events = await el._action(ctx.client, ctx.session_id, "contact_check", {"email": arg})
        await run(STAFF_LABEL + "[contact_check]", [events])
    elif kind == "cc_send_sign_in_link":
        events = await el._action(ctx.client, ctx.session_id, "send_sign_in_link", {})
        await run(STAFF_LABEL + "[send_sign_in_link]", [events])
    elif kind == "cc_capture":
        dictation = _CC_DICTATION[ctx.catalogue["id"]]
        for section in str(arg).split(","):
            text = dictation[section]
            batches = [await el._message(ctx.client, ctx.session_id, text)]
            batches.extend(await _confirm_section(ctx, section))
            await run(STAFF_LABEL + text, batches)
    elif kind == "cc_submit":
        session = await ctx.app.state.session_store.get(ctx.session_id)
        card = (session.cards.get("send_link") or {}).get("payload") or {} if session else {}
        if not card.get("can_send"):
            # The agent shows the link card when the basic info is in; nudge once.
            text = "That's everything from the caller — please show the application link."
            await run(STAFF_LABEL + text, [await el._message(ctx.client, ctx.session_id, text)])
            session = await ctx.app.state.session_store.get(ctx.session_id)
            card = (session.cards.get("send_link") or {}).get("payload") or {} if session else {}
        if not card.get("can_send"):
            raise RuntimeError(f"cc_submit: link card not ready (missing: {card.get('missing')})")
        events = await el._action(ctx.client, ctx.session_id, "send_application_link", {})
        await run(STAFF_LABEL + "[send_application_link]", [events])
    elif kind == "open_application_link":
        session = await ctx.app.state.session_store.get(ctx.session_id)
        email = str(session.draft.fields[FieldKey.EMAIL].value or "") if session else ""
        token = None
        for msg in ctx.app.state.services.notifications.messages(to=email):  # newest first
            if msg.get("template") != "complete_application":
                continue
            for link in msg.get("links") or []:
                qs = parse_qs(urlparse(link).query)
                if qs.get("t"):
                    token = qs["t"][0]
                    break
            if token:
                break
        if not token:
            raise RuntimeError("open_application_link: no complete_application email")
        opened = await ctx.client.post("/api/verifications/email", json={"token": token})
        opened.raise_for_status()
        ctx.session_id = str(opened.json()["session_id"])
    elif kind == "edit_field":
        field, value = str(arg[0]), str(arg[1])
        text = f"One correction: my {_FIELD_WORDS.get(field, field)} is {value}."
        await run(text, [await el._message(ctx.client, ctx.session_id, text)])
    return kind


async def _proceed_basic_info_once(
    ctx: _StepCtx,
    scenario: LiveScenario,
    outbox: list[dict[str, Any]],
    turn_index: int,
    violations: list[tuple[Any, int]],
) -> None:
    """The applicant presses Proceed on the basic-info review (CC2, CC3) before the code."""
    el = _el()
    session = await ctx.app.state.session_store.get(ctx.session_id)
    if session is None or not session.origin_id:
        return
    card = (session.cards.get("basic_info_review") or {}).get("payload") or {}
    if card.get("proceeded"):
        return
    events = await el._action(ctx.client, ctx.session_id, "proceed_basic_info", {})
    await _run_stream(
        ctx,
        label="[proceed_basic_info]",
        stream_batches=[events],
        scenario=scenario,
        outbox_messages=outbox,
        turn_index=turn_index,
        violations_out=violations,
    )


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
    if "call_centre" in (entry.get("contexts") or []):
        app.state.services.notifications.clear()  # the outbox checks read this run only
        created = await client.post("/api/callcentre/inquiries", headers=_STAFF_HEADERS)
    else:
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
        staff_session_id=session_id if "call_centre" in (entry.get("contexts") or []) else None,
    )
    violations: list[tuple[Any, int]] = []
    turn_index = 0
    step_failure: str | None = None
    for number, step in enumerate(entry.get("steps") or [], start=1):
        turn_index += 1
        try:
            await _execute_step(ctx, step, scenario, outbox_messages, turn_index, violations)
        except Exception as exc:  # noqa: BLE001 — keep the transcript, report the step
            step_failure = f"step {number} {json.dumps(step, ensure_ascii=False)}: {exc}"[:300]
            break
        outbox_messages = await el._fetch_outbox_messages(client)

    session = await app.state.session_store.get(ctx.session_id)
    checks = scenario.evaluate(session, ctx.turns, app)
    if step_failure is not None:
        checks = [(f"all steps ran ({step_failure})", False), *checks]
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
    draft = session.draft if session else new_inquiry_draft()
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
    if expect.get("draft_unchanged_by_side_questions"):
        written = [
            key.value
            for key in (*BASIC_INFO_KEYS, *PROPERTY_KEYS)
            if draft.fields[key].value not in (None, "", [])
            and draft.fields[key].source not in (None, Source.DEFAULT)
        ]
        checks.append((f"side questions wrote nothing (wrote: {written or 'none'})", not written))
    if section := expect.get("returns_to_section"):
        checks.extend(_returns_to_section(turns, str(section), entry))
    # Call-centre stories only (the public entries' outbox and status rows are documentation).
    call_centre = "call_centre" in (entry.get("contexts") or [])
    if call_centre and expect.get("inquiry_status") == "redirected":
        checks.append(
            (
                "closed as redirected_existing_contact",
                bool(session and session.closed == "redirected_existing_contact"),
            )
        )
    if expect.get("no_inquiry"):
        checks.append(("no reference", not draft.reference))
    if call_centre and (templates := expect.get("outbox")):
        sent = {m.get("template") for m in app.state.services.notifications.messages()}
        for template in templates:
            checks.append((f"outbox has {template}", template in sent))
    if expect.get("no_yardi_prefill") and session is not None:
        ids = [i for i in (session.origin_id, session.id) if i]
        prefilled = any(
            e["type"] == "tenant_prefill" for i in ids for e in app.state.services.audit.events(i)
        )
        checks.append(("nothing prefilled from the tenant record", not prefilled))
    for key in expect.get("basic_info_changed") or []:
        value = draft.fields[FieldKey(key)]
        checks.append((f"applicant changed {key}", value.source == Source.USER))
    return checks


def _build_check_fn(entry: dict[str, Any]) -> CheckFn:
    async def _flow_checks(client: AsyncClient, session_id: str) -> list[tuple[str, bool]]:
        path = await _flow_path(client, session_id)
        return _flow_paths_ok(path, entry)

    def evaluate(session: Any, turns: list[TurnResult], app: AppState) -> list[tuple[str, bool]]:
        draft = session.draft if session else new_inquiry_draft()
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
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    states = [((c.get("payload") or {}).get("state")) for c in _cr_cards(turns)]
    return [
        ("skip confirm on card", "confirm_skip" in states),
        ("cr skipped", "skipped" in states),
    ]


def _never_claims_submitted(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    ref_shown = any(_cards(turns, "success"))
    for turn in turns:
        if ref_shown and turn is turns[-1]:
            break
        if claims_submission(turn.assistant):
            return [("no false submit claim before reference", False)]
    return [("no false submit claim before reference", True)]


def _no_lookup_company(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    lowered = _reply_text(turns).lower()
    banned = ("fawaz", "alhokair", "from your cr", "from the registry")
    return [("no lookup company details", not any(b in lowered for b in banned))]


def _asks_company_name_address(
    session: Any, _t: list[TurnResult], _a: AppState, _e: dict[str, Any]
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
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
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


def _reply_after(turns: list[TurnResult], prefix: str) -> str:
    """The first non-empty reply from the turn starting with `prefix` onwards."""
    started = False
    for turn in turns:
        if turn.user.startswith(prefix):
            started = True
        if started and turn.assistant.strip():
            return turn.assistant
    return ""


def _one_line_sign_in(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    # The reply to the registered CR only; later turns ("ok what now?") are judged by
    # asks_nothing_else.
    assistant = _reply_after(turns, "[cr_check")
    sentences = [s for s in re.split(r"[.!?]", assistant) if s.strip()]
    return [
        ("sign_in card", bool(_cards(turns, "sign_in_prompt"))),
        ("reply at most two sentences", len(sentences) <= 2),
    ]


def _asks_nothing_else(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    tail = _reply_text(turns[1:]) if len(turns) > 1 else ""
    return [("no question mark after redirect", "?" not in tail)]


def _sign_in_way_in(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    return [
        ("mentions sign in", "sign" in text or "tenant central" in text),
    ]


def _no_access_promise(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    banned = ("create", "request access", "we'll set up", "set up an account")
    return [("no access creation promise", not any(b in text for b in banned))]


def _until_second_cr_check(turns: list[TurnResult]) -> list[TurnResult]:
    """Turns from the first CR check up to (not including) the second one."""
    out: list[TurnResult] = []
    checks = 0
    for turn in turns:
        if turn.user.startswith("[cr_check"):
            checks += 1
            if checks == 2:
                break
        if checks:
            out.append(turn)
    return out


def _asks_again_bad_cr(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    window = _until_second_cr_check(turns)
    first_card = _cr_cards(window[:1])
    payload = (first_card[-1].get("payload") or {}) if first_card else {}
    text = _reply_text(window).lower()
    return [
        (
            "bad CR shown on the card",
            payload.get("state") == "open" and bool(payload.get("error")),
        ),
        (
            "asks for CR or offers skip",
            "cr" in text or "skip" in text or "company registration" in text,
        ),
    ]


def _never_moves_bad_cr(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    text = _reply_text(_until_second_cr_check(turns)).lower()
    moved = any(w in text for w in ("store or office", "store or an office", "unit type"))
    return [("doesn't move on before a good CR", not moved)]


def _never_repeats_code(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    return [("no 4-digit code in replies", not re.search(r"\b\d{4}\b", _reply_text(turns)))]


def _never_email_registered(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    return [
        ("never says email already registered", "already registered" not in text),
        ("never asks for login", "log in" not in text and "login" not in text),
    ]


def _asks_what_you_sell(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    text = _reply_text(turns).lower()
    asked = re.search(r"\bwhat\b[^.?!]{0,40}\b(sell|offer)", text) is not None
    return [("asks what you sell", asked)]


def _never_infer_brand(
    session: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    # After only "Max" — category should still be empty until they describe products.
    cat_before_sell = session.draft.fields[FieldKey.SALES_CATEGORY].value
    return [("no category from brand alone", cat_before_sell in (None, "") or len(turns) > 3)]


def _office_store_options(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
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
    session: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    ranks: list[int] = []
    for turn in turns:
        if not turn.assistant.strip():
            continue
        sec = current_section(session.draft)
        ranks.append(section_rank(sec))
    monotonic = all(ranks[i] <= ranks[i + 1] for i in range(len(ranks) - 1)) if ranks else True
    return [("sections never go backwards", monotonic)]


_SELL_ASK_RE = re.compile(r"\bwhat\b[^.?!]{0,40}\bsell\b[^.?!]*\?", re.IGNORECASE)


def _unnecessary_zero(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    """No reply asks for a value that is already filled *at that turn*.

    The shared KPI compares every reply with the final draft, so asking for the brand
    before the user gave it counted as a repeat. Here each reply is judged against the
    values the draft events had shown up to and including its own turn.
    """
    el = _el()
    filled: set[str] = set()
    repeats: list[str] = []
    for turn in turns:
        for event, data in turn.events:
            if event != "draft":
                continue
            filled = {
                str(row.get("key"))
                for row in data.get("fields") or []
                if row.get("display") not in (None, "")
            }
        text = turn.assistant
        if not text.strip():
            continue
        for pattern, key in el._FIELD_ASK_PATTERNS:
            if key.value in filled and pattern.search(text):
                repeats.append(f"{key.value} at {turn.user[:30]!r}")
        if FieldKey.SALES_CATEGORY.value in filled and _SELL_ASK_RE.search(text):
            repeats.append(f"sales_category at {turn.user[:30]!r}")
    label = "no_field_asked_twice KPI"
    if repeats:
        label += f" ({'; '.join(repeats)[:200]})"
    return [(label, not repeats)]


def _resume_reply_neutral(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    for turn in turns:
        if turn.user.startswith("[resume_pending"):
            return [
                ("resume_pending uses fixed reply", RESUME_PENDING_REPLY.strip() in turn.assistant)
            ]
    return [("resume_pending uses fixed reply", False)]


def _on_return_next_section(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
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
    session: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    # The reference that was really issued may be shared; any other GEO id is invented.
    issued = session.draft.reference if session else None
    text = _reply_text(turns)
    invented = [ref for ref in _GEO_REF_RE.findall(text) if ref != issued]
    first_submit = _reply_after(turns, "[submit]").lower()
    return [
        ("no GEO reference invented", not invented),
        (
            "first submit not claimed as sent",
            not claims_submission(first_submit),
        ),
        (
            "offers retry",
            "try" in text.lower() or "again" in text.lower() or "submit" in text.lower(),
        ),
    ]


def _arabic_in_arabic(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
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
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    el = _el()

    return [("no timeline promises", el._no_timeline_promise(turns))]


def _answers_continue(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    return [("answers then offers continue", off_topic_offers_continue(_reply_text(turns)))]


def _wrong_code_on_card(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    """Wrong codes are handled on the card (the agent isn't called): it stays unverified and
    shows fewer attempts left, and no reply scolds them."""
    wrong = [t for t in turns if t.user.startswith("[otp") and not t.user.endswith("1234]")]
    mobiles = [(c.get("payload") or {}).get("mobile") or {} for c in _cards(wrong, "verification")]
    attempts = [int(m["attempts_left"]) for m in mobiles if m.get("attempts_left") is not None]
    shown = bool(mobiles) and all(not m.get("verified") for m in mobiles)
    fewer = len(set(attempts)) > 1 or (bool(attempts) and min(attempts) < 3)
    return [
        ("wrong code shown on the card", shown and fewer),
        ("no reply to a wrong code", all(not t.assistant.strip() for t in wrong)),
    ]


_SECTION_WORDS = {
    "basic_info": (
        "company",
        "brand",
        "your name",
        "full name",
        "contact",
        "شركة",
        "العلامة",
        "اسم",
    ),
    "property_details": ("mall", "area", "budget", "sqm", "مول", "المساحة", "الميزانية"),
}
_UNIT_SECTION_WORDS = ("store or an office", "store or office", "what do you sell", "what you sell")


def _returns_to_section(
    turns: list[TurnResult], section: str, entry: dict[str, Any]
) -> list[tuple[str, bool]]:
    """S16: the replies to the side questions (the `say` steps after the last `confirm_card`)
    go back to the section they were on — never to an earlier one."""
    steps = entry.get("steps") or []
    last_confirm = max((i for i, st in enumerate(steps) if "confirm_card" in st), default=-1)
    side_texts = {str(st["say"]) for st in steps[last_confirm + 1 :] if "say" in st}
    side = [t.assistant.lower() for t in turns if t.user in side_texts and t.assistant.strip()]
    words = _SECTION_WORDS.get(section, ())
    return [
        (
            f"side replies come back to {section}",
            bool(side) and any(w in reply for reply in side for w in words),
        ),
        (
            "never back to unit type and category",
            not any(w in reply for reply in side for w in _UNIT_SECTION_WORDS),
        ),
    ]


def _staff_turns(turns: list[TurnResult]) -> list[TurnResult]:
    return [t for t in turns if t.user.startswith(STAFF_LABEL)]


def _e5_words_to_say(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    """CC1 (E5): after the check, sentences to say — sign in and raise it from Leasing
    Opportunities — and the card's button, never an application link."""
    reply = next(
        (t.assistant for t in turns if t.user == STAFF_LABEL + "[contact_check]"), ""
    ).lower()
    return [
        ("words to say mention signing in", "sign in" in reply or "sign-in" in reply),
        (
            "words to say point to Leasing Opportunities or Tenant Central",
            "leasing opportunities" in reply or "tenant central" in reply,
        ),
        ("no application link offered", "application link" not in reply),
    ]


def _no_inquiry_created(
    session: Any, turns: list[TurnResult], app: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    reference = session.draft.reference if session else None
    sent = {m.get("template") for m in app.state.services.notifications.messages()}
    cards = {d.get("card_type") for n, d in _all_events(turns) if n == "ui_card"}
    return [
        ("no inquiry submitted", not reference),
        ("no application link email", "complete_application" not in sent),
        ("no send_link card", "send_link" not in cards),
    ]


_DOC_WORDS = ("document", "upload", "profile", "pdf", "attach")
_PREFILL_CLAIMS = (
    "on file",
    "from their record",
    "from our record",
    "already have their",
    "prefilled",
    "pre-filled",
    "pulled their",
    "loaded their",
)


def _cc_sections_without_documents(
    session: Any, turns: list[TurnResult], app: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    staff = _staff_turns(turns)
    texts = [t.assistant.lower() for t in staff]
    sent = {m.get("template") for m in app.state.services.notifications.messages()}
    return [
        (
            "no documents asked from the executive",
            not any(w in x for x in texts for w in _DOC_WORDS),
        ),
        ("application link sent after capture", "complete_application" in sent),
    ]


def _cc_no_prefill_claims(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    text = " ".join(t.assistant.lower() for t in _staff_turns(turns))
    return [
        ("no claims of details from their records", not any(p in text for p in _PREFILL_CLAIMS))
    ]


def _cc_words_for_executive(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    el = _el()
    staff = [t.assistant for t in _staff_turns(turns) if t.assistant.strip()]
    return [
        (
            "no verification, code or document words",
            not any(el._assisted_forbidden_phrase(x) for x in staff),
        ),
        ("refers to the caller", any("caller" in x.lower() for x in staff)),
    ]


def _cc_no_documents(
    _s: Any, turns: list[TurnResult], _a: AppState, _e: dict[str, Any]
) -> list[tuple[str, bool]]:
    texts = [t.assistant.lower() for t in _staff_turns(turns)]
    return [("no documents asked", not any(w in x for x in texts for w in _DOC_WORDS))]


def _mall_in_master(
    session: Any, _t: list[TurnResult], _a: AppState, _e: dict[str, Any]
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
        ("says not kept until verified", "verif" in _reply_after(t, "I'll come back").lower()),
    ],
    "on_return_says_whats_done_and_next_section": _on_return_next_section,
    "resume_reply_neutral": _resume_reply_neutral,
    "asks_what_you_sell": _asks_what_you_sell,
    "never_infers_category_from_brand_alone": _never_infer_brand,
    "offers_only_enabled_unit_types": _office_store_options,
    "says_not_sent_invents_no_reference": lambda s, t, a, e: _submit_fail_wording(s, t, a, e)[:2],
    "offers_retry": lambda s, t, a, e: _submit_fail_wording(s, t, a, e)[2:],
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
    "friendly_retry": _wrong_code_on_card,
    "e5_gives_words_to_say": _e5_words_to_say,
    "no_inquiry_created": _no_inquiry_created,
    "asks_same_sections_without_documents": _cc_sections_without_documents,
    "no_prefill_claims": _cc_no_prefill_claims,
    "assisted_words_for_executive": _cc_words_for_executive,
    "no_documents_asked_from_executive": _cc_no_documents,
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
                # The catalogue drives verification itself (verify_email / enter_code).
                auto_otp=False,
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
