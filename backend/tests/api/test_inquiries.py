import pytest
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_inquiry_status_unknown(client) -> None:
    response = await client.get("/api/inquiries/GEO-STR-000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "reference_not_found"


@pytest.mark.asyncio
async def test_inquiry_status_known(app) -> None:
    from app.security import tokens

    master = load_master_data()
    draft = new_inquiry_draft()
    reference = app.state.services.submit.submit(draft, master)
    token, _ = tokens.issue(
        app.state.settings.token_secret, "track", reference, ttl_seconds=60, data={"i": "s"}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.get(f"/api/inquiries/{reference}", params={"t": token})
        no_token = await http.get(f"/api/inquiries/{reference}")

    assert response.status_code == 200
    body = response.json()
    assert body["reference"] == reference
    assert body["status"] == "under_review"
    assert "waiting for review" in body["summary"]
    assert len(body["steps"]) == 3
    assert body["steps"][0]["state"] == "done"
    assert body["steps"][1]["state"] == "current"
    assert body["current_stage"] == "first_review"
    # A guessable reference alone exposes nothing (L3 §3.4).
    assert no_token.status_code == 404
