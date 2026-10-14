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
