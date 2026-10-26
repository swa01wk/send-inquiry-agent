# Step 13 — Durable inquiry state

Read first: @docs/specs/m0-modular-core.md (section 5) @backend/app/sessions.py @backend/app/agent/events.py @backend/app/api/chat.py @backend/app/api/documents.py

**Start in plan mode:** propose the repository interface, the table schema and the migration, and how `SessionStore` adapts. Wait for approval before writing code.

## Goal
Make an inquiry survive restarts and multiple workers, without changing any API or SSE contract.

## Build
1. `app/store/models.py`: the `Inquiry` and `InquiryStatus` models from spec §5.1. Move `cards_shown`, `confirm_card_keys` and `card_counter` off `Session` onto `Inquiry`.
2. `app/store/repository.py`: the `InquiryRepository` protocol (§5.2), with two implementations:
   - `InMemoryInquiryRepository`;
   - `PostgresInquiryRepository` (SQLAlchemy 2 async, psycopg 3).

   Saves use an optimistic `version`; the turn lease is the conditional `UPDATE` in §5.2.
3. Alembic set-up and migration `0001_inquiries` for `inquiries` and `inquiry_events` (§5.3).
4. `SessionStore` becomes an adapter over the repository. Keep its method names, `SessionNotFound` → 404 and `TurnInProgress` → 409.
5. `run_turn`:
   - renews the lease every 30 s while streaming;
   - saves the inquiry at the end of the turn;
   - on `VersionConflict`, reloads once and retries the save.
6. The documents router takes the turn lease for upload and delete.
7. `build_graph(checkpointer=…)`: `MemorySaver` or `AsyncPostgresSaver` (`thread_id` = inquiry id), chosen by `STATE_BACKEND`.
8. `agent_node` trims history to `AGENT_HISTORY_MESSAGES`, cutting only at a turn boundary (never between a tool call and its `ToolMessage`).
9. `purge_expired`:
   - drafts past `expires_at` become `abandoned`;
   - their checkpoints and uploads are deleted;
   - the audit trail is kept.

   Run it hourly from the app lifespan.
10. Add Postgres to `docker-compose.yml` and set `STATE_BACKEND`/`DATABASE_URL` for `make dev`. Add the config variables from §10.

## Tests
**Layers** (`docs/specs/testing-strategy.md`): BE (memory and Postgres), AGENT-DET (parity), INT.
- Repository contract tests run against both implementations; Postgres tests are marked `@pytest.mark.postgres` and use `TEST_DATABASE_URL`.
- `tests/durability/test_restart.py`: run two turns, rebuild the app on the same database, run a third turn on the same `session_id`. Draft, cards and history continue.
- Lease: a second concurrent turn gets 409; an expired lease can be taken over.
- History trimming never orphans a tool call.

## Acceptance criteria
- The parity suite (step 12) is green with both backends.
- Gate G2 passes.
- No router or frontend change was needed.
- `docs/STATUS.md` updated (row 13).

## Verify
```
cd backend && uv run pytest -q && STATE_BACKEND=postgres TEST_DATABASE_URL=postgresql+psycopg://… uv run pytest -m postgres -q
```
