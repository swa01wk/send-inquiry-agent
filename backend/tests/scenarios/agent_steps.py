"""Predetermined ScriptedChatModel steps for scenario tests (from catalogue)."""

from __future__ import annotations

from typing import Any

from tests.scenarios.catalogue import model_steps_for


def tool_step(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [
            {
                "name": name,
                "args": args,
                "id": call_id,
                "type": "tool_call",
            }
        ],
    }


def say(content: str) -> dict[str, Any]:
    return {"content": content}


HAPPY_PATH_CR_STEPS: list[dict[str, Any]] = model_steps_for("happy-path-cr")
SKIP_CR_STEPS: list[dict[str, Any]] = model_steps_for("skip-cr")
EXISTING_CR_STEPS: list[dict[str, Any]] = model_steps_for("existing-cr-sign-in")
MANY_FIELDS_STEPS: list[dict[str, Any]] = model_steps_for("many-fields-one-message")
UNIT_TYPE_CORRECTION_STEPS: list[dict[str, Any]] = model_steps_for("unit-type-correction")
SMALL_TALK_STEPS: list[dict[str, Any]] = model_steps_for("small-talk")
FAQ_STEPS: list[dict[str, Any]] = model_steps_for("faq-documents")
OFF_TOPIC_STEPS: list[dict[str, Any]] = model_steps_for("off-topic")
INJECTION_STEPS: list[dict[str, Any]] = model_steps_for("prompt-injection")
STATUS_LOOKUP_STEPS: list[dict[str, Any]] = model_steps_for("status-lookup")
MISSING_DOC_STEPS: list[dict[str, Any]] = model_steps_for("missing-doc")
REVIEW_EDIT_STEPS: list[dict[str, Any]] = model_steps_for("review-edit")
