# Step 18 — Simulated Cenomi: mock services, faults and the notification outbox

Read first: @docs/specs/l3-reliable-intake.md (sections 3.1, 3.4) @docs/specs/m0-modular-core.md (section 7.1) @backend/app/services/ @backend/app/services/container.py

**Start in plan mode:** list each mock, its scenario data, how faults are injected and how the gateway sees them, and the outbox model. Wait for approval before writing code.

## Goal
Every external Cenomi system behaves like the real one — state, realistic outcomes, failures on demand — behind the interfaces the real adapters will use, and every message the system sends can be seen in a dev inbox.

## Build
1. `INTEGRATIONS=mock|sandbox|live` selects implementations in `services/container.py`. `mock` is the default. `app/integrations/{sandbox,live}/` hold stubs that raise `NotImplementedError` naming the open question (spec §7).
2. Scenario data in `backend/app/data/mock_world/`, loaded at start-up:
   - `cr_registry.json`: today's three numbers unchanged, plus `1010333333` (new, Arabic company name), `1010999991` (timeout), `1010999992` (unavailable).
   - Move `MockCrService`'s hard-coded numbers into this file.
3. Mocks per spec §3.1 table: CR registry, email, SMS, admin-platform inbox (`submit`/`lookup`), status (stage, next owner, open requests, last change from the workflow status), call centre, storage.
4. Fault injection:
   - `MOCK_FAULTS` env, `service:kind[:count]`, kinds `timeout`, `unavailable`, `rejected`;
   - the `X-Mock-Faults` header on `POST /api/sessions`, honoured only when `AGENT_MODE=scripted` (like `X-Test-Scenario`);
   - `MOCK_LATENCY_MS`.

   Mocks raise the same exception types a real client would, so the gateway maps them to `GatewayError` kinds.
5. Notifications:
   - `NotificationService.send(template, to, context)`; templates in `app/notifications/templates/*.txt` rendered with `string.Template`; each declares `kind` (`information` | `action_required`);
   - templates now: `email_verification_link`, `sms_otp`, `resume_link`, `submission_email`, `submission_sms`;
   - the email-link and OTP mocks deliver through it;
   - `MockNotificationService` keeps an outbox `{id, inquiry_id, channel, to, template, kind, subject, body, links, created_at}`.
6. Dev tools (only when `DEV_TOOLS=true`; refuse to start if `DEV_TOOLS=true` and `INTEGRATIONS!=mock`):
   - `GET /api/dev/outbox?to=` and `DELETE /api/dev/outbox`;
   - frontend `/dev/inbox` (add `react-router-dom` here; spec §3.2 says why) listing messages per recipient with clickable links.
7. `CallCentreService.create_case(payload, reason, summary)` mock (used in step 21); cases show in the dev inbox.
8. `tests/contract/`: one module per service, marked `contract` (runs against mocks) and reusable with `sandbox` later. Each covers success, a definite rejection, a timeout and a duplicate call with the same idempotency key.
9. Update `docs/spec.md` (§8 services, §10 config, test hooks) and `docs/STATUS.md` (row 18).

## Tests
- Contract tests for every mock.
- A failure-path test for each step of the flow with the mock forced to fail: the inquiry stays resumable and the user gets a clear next step (E7).
- The outbox never appears in logs; `/api/dev/*` returns 404 when `DEV_TOOLS` is off.
- Frontend: the inbox renders messages and links.

## Acceptance criteria
- Gate E7 passes with mock faults.
- Tools and actions contain no mock-specific code.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/gateway tests/contract -q -m "not sandbox" && cd .. && make test && make lint
```
