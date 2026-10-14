import pytest
from app.api.cards import WELCOME_MESSAGE_1, WELCOME_MESSAGE_2, WELCOME_QUICK_REPLIES
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_session_welcome_copy_and_chips(client: AsyncClient) -> None:
    response = await client.post("/api/sessions")
    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    texts = [m["text"] for m in body["messages"]]
    assert texts == [WELCOME_MESSAGE_1, WELCOME_MESSAGE_2]

    assert len(body["cards"]) == 1
    card = body["cards"][0]
    assert card["card_id"] == "quick-replies"
    assert card["card_type"] == "quick_replies"
    labels = [opt["label"] for opt in card["payload"]["options"]]
    assert labels == [label for label, _, _, _ in WELCOME_QUICK_REPLIES]
    first = card["payload"]["options"][0]
    assert first["action"] == "focus_input"
    assert first["placeholder"] == "Type your 10-digit CR number"

    assert body["draft"]["phase"] == "gate"
    assert body["draft"]["changed_keys"] == []


@pytest.mark.asyncio
async def test_get_draft_unknown_session(client: AsyncClient) -> None:
    response = await client.get("/api/sessions/00000000-0000-0000-0000-000000000000/draft")
    assert response.status_code == 404
    err = response.json()["error"]
    assert err["code"] == "session_not_found"
