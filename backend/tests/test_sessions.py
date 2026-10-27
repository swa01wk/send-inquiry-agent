from datetime import UTC, datetime, timedelta

import pytest
from app.sessions import SessionNotFound, SessionStore


@pytest.mark.asyncio
async def test_session_create_get_touch():
    store = SessionStore(ttl_minutes=120)
    session = await store.create()
    fetched = await store.get(session.id)
    assert fetched.id == session.id

    touched = await store.touch(session.id)
    assert touched.last_seen >= session.last_seen


@pytest.mark.asyncio
async def test_session_ttl_expiry():
    store = SessionStore(ttl_minutes=30)
    session = await store.create()
    store._sessions[session.id].last_seen = datetime.now(tz=UTC) - timedelta(minutes=31)

    with pytest.raises(SessionNotFound):
        await store.get(session.id)

    with pytest.raises(SessionNotFound):
        await store.touch(session.id)


@pytest.mark.asyncio
async def test_snapshots_survive_restart(tmp_path):
    store = SessionStore(ttl_minutes=120, data_dir=str(tmp_path))
    session = await store.create()
    session.add_message("u_1", "user", "Hi, I'd like a kiosk")
    session.remember_card({"card_id": "verification", "card_type": "verification", "payload": {}})
    session.draft.email_verified = True
    store.save(session)

    restarted = SessionStore(ttl_minutes=120, data_dir=str(tmp_path))
    restored = await restarted.get(session.id)
    assert restored.transcript == session.transcript
    assert list(restored.cards) == ["verification"]
    assert restored.draft.email_verified is True


@pytest.mark.asyncio
async def test_revive_reaches_an_idle_session_by_link(tmp_path):
    store = SessionStore(ttl_minutes=30, data_dir=str(tmp_path))
    session = await store.create()
    store.save(session)
    store._sessions[session.id].last_seen = datetime.now(tz=UTC) - timedelta(minutes=31)
    with pytest.raises(SessionNotFound):
        await store.get(session.id)
    revived = await store.revive(session.id)
    assert revived.id == session.id
    assert (await store.get(session.id)).id == session.id


@pytest.mark.asyncio
async def test_revive_rejects_unknown_or_unsafe_ids(tmp_path):
    store = SessionStore(ttl_minutes=30, data_dir=str(tmp_path))
    for bad in ("../etc/passwd", "nope"):
        with pytest.raises(SessionNotFound):
            await store.revive(bad)
