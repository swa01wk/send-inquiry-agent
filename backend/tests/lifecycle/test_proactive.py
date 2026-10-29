"""Proactive work, thin (L5 §3.1–3.4): triggers at their thresholds and not before, once
per period, the notification policy, "Needs attention", and no status changes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.workflow.models import CaseStatus
from tests.lifecycle.conftest import APPLICANT, STORE_CENTRAL, act, outbox, submit_case

MANAGER = "rlm_store-manager"
STORE_WESTERN = "rlm_store-western"
CENTRAL_REVIEWER_EMAIL = "faisal.alqahtani@cenomi.example"
MANAGER_EMAIL = "abdulaziz.alshehri@cenomi.example"


def riyadh(hour: int, day: int = 2) -> datetime:
    """Riyadh wall-clock time (UTC+3) on a November day, as UTC."""
    return datetime(2026, 11, day, hour, tzinfo=UTC) - timedelta(hours=3)


def freeze(app, at: datetime) -> None:
    app.state.services.clock.freeze(at)


async def advance(client, hours: float) -> dict:
    response = await client.post("/api/dev/clock/advance", json={"hours": hours})
    assert response.status_code == 200, response.text
    return response.json()


async def attention(client, reviewer: str) -> dict:
    response = await client.get("/api/review/attention", headers={"X-Reviewer-Id": reviewer})
    assert response.status_code == 200, response.text
    return response.json()


def _items(data: dict, trigger: str) -> list[dict]:
    return [i for i in data["items"] if i["trigger"] == trigger]


async def test_stalled_review_fires_at_the_threshold_once(life) -> None:
    client, app = life
    freeze(app, riyadh(10))
    reference = await submit_case(client, app)

    await advance(client, 47)
    assert _items(await attention(client, STORE_CENTRAL), "stalled_review") == []
    assert outbox(app, template="review_stalled") == []

    tick = await advance(client, 2)  # 49 h in first review
    assert tick["raised"] == 1
    items = _items(await attention(client, STORE_CENTRAL), "stalled_review")
    assert len(items) == 1
    assert items[0]["reference"] == reference
    assert items[0]["stage_label"] == "First review"
    assert items[0]["age_hours"] >= 48
    stalled_mail = outbox(app, template="review_stalled")
    assert [m["to"] for m in stalled_mail] == [CENTRAL_REVIEWER_EMAIL]  # not the manager

    await advance(client, 5)
    await client.post("/api/dev/proactive/tick")
    data = await attention(client, STORE_CENTRAL)
    assert len(_items(data, "stalled_review")) == 1
    assert len(outbox(app, template="review_stalled")) == 1
    assert data["counts"]["raised"] == 1
    # Another region's reviewer doesn't see it.
    assert (await attention(client, STORE_WESTERN))["items"] == []


async def test_escalation_reaches_the_region_manager(life) -> None:
    client, app = life
    freeze(app, riyadh(10))
    await submit_case(client, app)
    await advance(client, 97)

    manager_view = await attention(client, MANAGER)
    assert manager_view["items"][0]["trigger"] == "escalation"  # escalations first
    assert [m["to"] for m in outbox(app, template="review_escalated")] == [MANAGER_EMAIL]
    reviewer_view = await attention(client, STORE_CENTRAL)
    assert _items(reviewer_view, "escalation") == []
    assert len(_items(reviewer_view, "stalled_review")) == 1


async def test_acting_on_the_case_resolves_the_flag_and_starts_a_new_period(life) -> None:
    client, app = life
    freeze(app, riyadh(10))
    reference = await submit_case(client, app)
    await advance(client, 49)
    assert (await act(client, STORE_CENTRAL, reference, "approve_first")).status_code == 200

    await client.post("/api/dev/proactive/tick")
    data = await attention(client, STORE_CENTRAL)
    assert _items(data, "stalled_review") == []  # the first-review flag is resolved

    await advance(client, 49)  # 49 h in second review: a new period
    stalled = _items(await attention(client, STORE_CENTRAL), "stalled_review")
    assert len(stalled) == 1
    assert stalled[0]["stage_label"] == "Lead — second review"


async def test_unanswered_request_drafts_a_reminder_for_approval(life) -> None:
    client, app = life
    freeze(app, riyadh(10))
    reference = await submit_case(client, app)
    await act(client, STORE_CENTRAL, reference, "approve_first")  # opens a contacts request

    await advance(client, 71)
    assert _items(await attention(client, STORE_CENTRAL), "applicant_reminder") == []
    await advance(client, 2)  # 73 h unanswered
    reminders = _items(await attention(client, STORE_CENTRAL), "applicant_reminder")
    assert len(reminders) == 1
    item = reminders[0]
    assert item["status"] == "awaiting_approval"
    assert item["tier"] == 2
    assert "Authorized Signatory and Billing Contact" in item["text"]
    assert reference in item["text"]
    assert outbox(app, APPLICANT, "applicant_reminder") == []

    edited = "Please add your Authorized Signatory and Billing Contact so we can continue."
    approved = await client.post(
        f"/api/review/attention/{item['id']}/approve",
        json={"text": edited},
        headers={"X-Reviewer-Id": STORE_CENTRAL},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "sent"
    sent = outbox(app, APPLICANT, "applicant_reminder")
    assert len(sent) == 1
    assert edited in sent[0]["body"]
    assert any("/inquiry/case?t=" in link for link in sent[0]["links"])

    again = await client.post(
        f"/api/review/attention/{item['id']}/approve",
        json={},
        headers={"X-Reviewer-Id": STORE_CENTRAL},
    )
    assert again.status_code == 409
    decisions = [
        e["payload"]["decision"]
        for e in app.state.services.audit.events(reference)
        if e["type"] == "proactive_decision"
    ]
    assert "awaiting_approval" in decisions and "sent" in decisions


async def test_reminder_approved_at_night_waits_for_the_morning(life) -> None:
    client, app = life
    freeze(app, riyadh(20))
    reference = await submit_case(client, app)
    await act(client, STORE_CENTRAL, reference, "approve_first")
    await advance(client, 75)  # 23:00 in Riyadh, 75 h unanswered
    item = _items(await attention(client, STORE_CENTRAL), "applicant_reminder")[0]

    held = await client.post(
        f"/api/review/attention/{item['id']}/approve",
        json={},
        headers={"X-Reviewer-Id": STORE_CENTRAL},
    )
    assert held.json()["status"] == "held"
    assert held.json()["send_after"].startswith("2026-11-06T05:00")  # 08:00 Riyadh
    assert outbox(app, APPLICANT, "applicant_reminder") == []

    morning = await client.post("/api/dev/clock/to-morning")
    assert morning.json()["sent"] == 1
    assert len(outbox(app, APPLICANT, "applicant_reminder")) == 1


async def test_dismiss_needs_a_listed_reason_and_stops_the_item_for_the_period(life) -> None:
    client, app = life
    freeze(app, riyadh(10))
    await submit_case(client, app)
    await advance(client, 49)
    item = _items(await attention(client, STORE_CENTRAL), "stalled_review")[0]
    headers = {"X-Reviewer-Id": STORE_CENTRAL}

    bad = await client.post(
        f"/api/review/attention/{item['id']}/dismiss", json={"reason": "bored"}, headers=headers
    )
    assert bad.status_code == 400
    ok = await client.post(
        f"/api/review/attention/{item['id']}/dismiss",
        json={"reason": "already_handled"},
        headers=headers,
    )
    assert ok.status_code == 200
    await advance(client, 10)
    data = await attention(client, STORE_CENTRAL)
    assert _items(data, "stalled_review") == []
    assert data["counts"]["dismissed"] == {"already_handled": 1}
    assert data["counts"]["raised"] == 1
    other = await client.post(
        f"/api/review/attention/{item['id']}/dismiss",
        json={"reason": "other"},
        headers={"X-Reviewer-Id": STORE_WESTERN},
    )
    assert other.status_code == 404


async def test_no_proactive_path_changes_a_case(life, monkeypatch: pytest.MonkeyPatch) -> None:
    client, app = life
    freeze(app, riyadh(10))
    reference = await submit_case(client, app)
    await act(client, STORE_CENTRAL, reference, "approve_first")
    before = app.state.services.cases.get(reference).model_dump(mode="json")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a proactive path tried to change a case")

    monkeypatch.setattr("app.workflow.service.transition", forbidden)
    monkeypatch.setattr("app.workflow.service.apply_event", forbidden)
    await advance(client, 73)
    data = await attention(client, STORE_CENTRAL)
    reminder = _items(data, "applicant_reminder")[0]
    await client.post(
        f"/api/review/attention/{reminder['id']}/approve",
        json={},
        headers={"X-Reviewer-Id": STORE_CENTRAL},
    )
    stalled = _items(data, "stalled_review")[0]
    await client.post(
        f"/api/review/attention/{stalled['id']}/dismiss",
        json={"reason": "not_needed"},
        headers={"X-Reviewer-Id": STORE_CENTRAL},
    )
    after = app.state.services.cases.get(reference)
    assert after.status == CaseStatus.SECOND_REVIEW
    assert after.model_dump(mode="json") == before


async def test_reset_starts_the_demo_clean(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await advance(client, 49)
    assert (await client.get("/api/dev/clock")).json()["offset_hours"] == 49

    assert (await client.post("/api/dev/reset")).json() == {"reset": True}
    assert app.state.services.cases.get(reference) is None
    assert app.state.services.notifications.messages() == []
    assert app.state.services.attention.all() == []
    assert (await client.get("/api/dev/clock")).json()["offset_hours"] == 0
    assert (
        await client.get("/api/review/cases", headers={"X-Reviewer-Id": STORE_CENTRAL})
    ).json() == []
    # And the app still works afterwards.
    assert (await submit_case(client, app)).startswith("GEO-")
