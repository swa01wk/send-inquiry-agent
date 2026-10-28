"""Reviewer directory (L4 §3.2): who reviews which queue, from mock scenario data.

One reviewer per queue (role × region), a manager per role covering every region (for
L5 escalation), and the call-centre and guest-service staff used from Day 5.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.workflow.machine import Actor

REVIEWERS_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_world" / "reviewers.json"


class Reviewer(BaseModel):
    id: str
    kind: Literal["reviewer", "staff"]
    name: str
    email: str
    role: str
    regions: list[str] = Field(default_factory=list)
    manager: bool = False

    def actor(self) -> Actor:
        return Actor(kind=self.kind, id=self.id, role=self.role, regions=list(self.regions))


@lru_cache
def _load(path: str) -> tuple[Reviewer, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(Reviewer.model_validate(r) for r in raw["reviewers"])


class ReviewerDirectory:
    def __init__(self, path: Path = REVIEWERS_PATH) -> None:
        self._reviewers = _load(str(path))

    def all(self) -> list[Reviewer]:
        return list(self._reviewers)

    def get(self, reviewer_id: str) -> Reviewer | None:
        return next((r for r in self._reviewers if r.id == reviewer_id), None)

    def for_queue(self, role: str, region: str) -> list[Reviewer]:
        """Reviewers who act on this queue (managers included)."""
        return [
            r
            for r in self._reviewers
            if r.kind == "reviewer" and r.role == role and region in r.regions
        ]
