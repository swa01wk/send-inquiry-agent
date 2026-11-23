"""Shared predicates for live eval scripts (not used in production graph)."""

from __future__ import annotations

from typing import Any


def off_topic_offers_continue(text: str) -> bool:
    """True when a decline still invites the user back to the leasing flow."""
    lowered = text.lower()
    if any(
        phrase in lowered
        for phrase in (
            "continue",
            "carry on",
            "get started",
            "take it from there",
        )
    ):
        return True
    if "help" in lowered and ("send" in lowered or "lease" in lowered):
        return True
    if "tell me" in lowered and any(w in lowered for w in ("brand", "lease", "open")):
        return True
    if ("inquiry" in lowered or "inquiries" in lowered) and any(
        phrase in lowered
        for phrase in (
            "tell me",
            "send me",
            "if you",
            "if you're",
            "i can help",
            "happy to",
            "we can",
            "i'll take",
        )
    ):
        return True
    return False


# ---- 18 Nov demo B1 (docs/specs/demo-18nov-feedback.md §6) ------------------------------


def speaks_of_leasing_team_in_third_person(text: str) -> bool:
    """True when a reply says "our leasing team" or "the leasing team will" (guard rule 9)."""
    from app.agent.guard import third_person_team_note

    return third_person_team_note(text) is not None


def choice_option_problems(
    payloads: list[dict[str, Any]], known_ids: set[str], *, limit: int
) -> list[str]:
    """What is wrong with `choice` card payloads: unknown ids, too many or no options."""
    problems: list[str] = []
    for payload in payloads:
        values = [str(o.get("value")) for o in payload.get("options") or [] if isinstance(o, dict)]
        if not 1 <= len(values) <= limit:
            problems.append(f"{len(values)} options (want 1–{limit})")
        problems.extend(f"unknown id {v}" for v in values if v not in known_ids)
    return problems


def confirm_rows_without_value_button(payloads: list[dict[str, Any]]) -> list[str]:
    """Keys of `confirm_fields` rows that wait for a tap but have no value button."""
    missing: list[str] = []
    for payload in payloads:
        for row in payload.get("fields") or []:
            if not isinstance(row, dict) or row.get("confirmed") or not row.get("display"):
                continue
            if not row.get("value_label"):
                missing.append(str(row.get("key")))
    return missing
