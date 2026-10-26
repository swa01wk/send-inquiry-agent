# Step 29 — Event engine, simulated clock and notification policy

Read first: @docs/specs/l5-governed-proactivity.md (sections 1, 3.1, 3.3) @backend/app/audit/ @backend/app/notifications/ @backend/app/policy/

**Start in plan mode:** show the engine loop (events + tick), the `Clock` interface, the `proactive:` policy schema, the `proactive_items` table and `NotificationPolicy.check`. Wait for approval before writing code.

## Goal
The foundation for proactivity: time and events the system can reason over, and one gate every proactive message must pass.

## Build
1. `app/proactive/clock.py`: `Clock`, `SystemClock`, `SimulatedClock`; `POST /api/dev/clock/advance {hours}` (dev tools only) advances and runs a tick.
2. `app/proactive/engine.py`: reads `inquiry_events` from a stored cursor plus a periodic tick (`PROACTIVE_TICK_SECONDS`); evaluates triggers from the policy; writes `proactive_items` keyed by `(inquiry_id, trigger, period_key)`. Off unless `PROACTIVE_ENABLED=true`.
3. Policy `proactive:` section (Pydantic-validated): per trigger — enabled, thresholds, tier, template, throttle.
4. `app/proactive/policy.py`: `NotificationPolicy.check(message, case, now)` → `send | hold_until(t) | throttle | needs_approval | blocked_opt_out`, per spec §3.3. Every outcome audited.
5. Opt-out: token purpose `optout`, `GET /api/optout?t=` sets `Inquiry.proactive_opt_out`; a small confirmation page.
6. Migration for `proactive_items` and the cursor. Update `docs/spec.md` and `docs/STATUS.md` (row 29).

## Tests (`tests/proactive/`)
- `test_policy.py`: each tier; quiet hours across midnight; the per-case throttle; opt-out blocks proactive but not transactional.
- Engine idempotence: repeated ticks and a restart don't duplicate items.
- Simulated clock: advancing fires due triggers and nothing else.

## Acceptance criteria
- Gate Y2 passes at the policy level.
- With `PROACTIVE_ENABLED=false`, behaviour is unchanged (parity, L3 and L4 stories green).

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/proactive tests/parity -q
```
