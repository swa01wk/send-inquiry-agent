# Step 18 — Integration adapters

Read first: @docs/specs/l3-reliable-intake.md (section 3.1) @docs/specs/m0-modular-core.md (section 7.1) @backend/app/services/

**Start in plan mode:** for each adapter, list what's known about the Cenomi system and what's still an open question (Q1–Q5). Build only to the agreed contract and mark the rest as TODO stubs.

## Goal
Real systems can replace each mock by configuration, with identical behaviour at the tool and action level.

## Build
1. `INTEGRATIONS=mock|sandbox|live` selects implementations in `services/container.py`. `mock` stays the default for dev and CI.
2. One adapter module per service under `app/integrations/`: CR lookup, email, SMS, submit and status, storage. Each:
   - implements the existing protocol;
   - calls out through the gateway with explicit timeouts;
   - maps provider errors to `GatewayError` kinds;
   - never logs PII.
3. `NotificationService.send_submission(reference, tracking_url, contact)` for the submission email and SMS (used in step 20).
4. `CallCentreService.create_case(payload, reason, summary)` with a mock (used in step 21).
5. A contract-test harness `tests/contract/` with one test module per adapter, marked `@pytest.mark.sandbox`, covering:
   - success;
   - a definite rejection;
   - a timeout;
   - a duplicate call with the same idempotency key.
6. A failure-path test for each step of the flow, with the adapter forced to fail: the inquiry stays resumable and the user gets a clear next step.

## Acceptance criteria
- Gate E7 passes with mocks forced to fail.
- Contract tests pass against every sandbox that's available; missing sandboxes are listed in `docs/specs/l3-reliable-intake.md` §7 with their open question.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/gateway tests/contract -q -m "not sandbox"
```
