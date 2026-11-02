"""Browser session handle state (transcript, cards, channel context)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HandleState(BaseModel):
    transcript: list[dict[str, str]] = Field(default_factory=list)
    cards: dict[str, dict[str, Any]] = Field(default_factory=dict)
    inquiry_seq: int = 1
    form_mode: bool = False
    mode: str = "intake"
    contacts_draft: list[dict[str, Any]] = Field(default_factory=list)
    created_by: str | None = None
    link_sent_to: str | None = None
    complete_nonce: str | None = None
    closed: str | None = None
    existing_cr_choice: str | None = None
    test_scenario: str | None = None
    script_step: int = 0
