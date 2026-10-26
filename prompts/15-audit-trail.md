# Step 15 — Audit trail

Read first: @docs/specs/m0-modular-core.md (section 8) @.cursor/rules/project.mdc (golden rule 8)

## Goal
Every case has an ordered, redacted record of what happened and why, ready for reviewers (L4) and for KPIs (L3).

## Build
1. `app/audit/log.py`:
   - `AuditLog.record(inquiry_id, type, actor, payload, correlation_id)`, append-only;
   - `seq` numbered per inquiry;
   - backed by `inquiry_events` (Postgres) or a list (memory).
2. `app/audit/redact.py`:
   - an allowlist of payload keys per event type;
   - unknown keys are dropped;
   - `code`, `token`, `email`, `mobile`, `landline` and `file_name` are always hashed (SHA-256, truncated) or dropped.
3. Record every event type in spec §8 at the place listed. `correlation_id` is one id per chat turn, created in the chat endpoint and passed through `RunnableConfig`.
4. Wrap the tools node so each tool call records `tool_called` (redacted args, result summary, latency) without changing tool code.
5. `scripts/audit_dump.py <inquiry_id>`: print the trail as a readable table.

## Tests
- `tests/audit/test_trail.py`: the CR happy path produces the expected ordered event types.
- Scan every event payload for the OTP code, the link token, the raw email and phone, and file names; none may appear.
- A guard retry records `guard_verdict` with `retried: true`.

## Acceptance criteria
- Gate G4 passes.
- Parity suite green.
- `docs/STATUS.md` updated (row 15).

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/audit tests/parity -q
```
