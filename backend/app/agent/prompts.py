"""System prompt assembly."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.messages import SystemMessage

from app.agent.bundles import next_bundle_hint
from app.domain.master import MasterData
from app.domain.models import InquiryDraft
from app.domain.summary import prompt_summary

_PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.md"


@lru_cache
def _static_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def clear_prompt_cache() -> None:
    """For tests after prompt file edits."""
    _static_prompt.cache_clear()


def build_system_message(
    draft: InquiryDraft,
    master: MasterData,
    cards_shown: list[str] | None = None,
) -> SystemMessage:
    dynamic = prompt_summary(draft, master)
    hint = next_bundle_hint(draft, cards_shown)
    content = f"{_static_prompt()}\n\n## Current state\n{dynamic}\n{hint}"
    return SystemMessage(content=content)
