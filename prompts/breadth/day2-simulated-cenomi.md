# Breadth Day 2 (Wed 28 Oct) — Simulated Cenomi, real verification, submit and tracking

Read first: @docs/DELIVERY-PLAN.md (§A2, §A5) @docs/specs/l3-reliable-intake.md (sections 3.1–3.4) @prompts/18-integration-adapters.md @prompts/19-email-link-resume.md @prompts/20-status-page-notifications.md

## Goal
The applicant gets real (simulated) emails and SMS, verifies by clicking the emailed link, can resume from it, submits once, and tracks the inquiry on a private page.

## Backend track (Claude's PR — don't build these)
- `data/mock_world/cr_registry.json` with the scenario CR numbers (L3 §3.1); `MockCrService` reads it.
- `MOCK_FAULTS` env and the `X-Mock-Faults` header (scripted mode only).
- `NotificationService.send(template, to, context)`, templates (`email_verification_link`, `sms_otp`, `resume_link`, `submission_email`, `submission_sms`), outbox; `GET`/`DELETE /api/dev/outbox` behind `DEV_TOOLS`.
- Signed tokens (stdlib `hmac`), purposes `verify_email`, `resume`, `track`.
- `POST /api/verifications/email {token}`; `POST /api/sessions/resume {token}` returning the session's messages, cards and draft (in-memory store; same session).
- Resend cooldown and hourly cap; `resend_available_at` on the verification card; note `resend_throttled <s>`.
- Submit once: a repeat `accept_and_submit` on a submitted inquiry returns the same reference and success card (note `submitted reference=… (repeat)`).
- On submit: `submission_email` and `submission_sms` to the outbox; `success.tracking_url` = `/inquiry/status/<ref>?t=<track token>`.
- `GET /api/inquiries/{reference}?t=` (token required) with stages, current stage, owner role, `waiting_on_you` (empty for now) and last change.
- **L3 core — durable drafts (capability 7):** `SessionStore` writes a JSON snapshot of every inquiry (draft, cards, messages needed for resume, case data, audit log) to `DATA_DIR` after each turn and action, and reloads it at start-up. A backend restart mid-inquiry continues the same session.
- **L3 core — audit (capability 10):** `AuditLog.record(inquiry_id, type, actor, payload)` with the M0 §8 event types (`user_message`, `ui_action`, `tool_called`, `field_written`, `field_confirmed`, `guard_verdict`, `verification_sent`, `verification_result`, `submit_attempt`, `submit_result`, `notification_sent`) and its redaction allowlist (no codes, tokens, raw contact details or file names). Dev-only `GET /api/dev/audit/{inquiry_id}`.
- **L3 core — reliable execution (capability 9):** one thin gateway around every mock call: a timeout per service and the four error kinds (`timeout`, `unavailable`, `rejected`, `invalid`) from M0 §7.1, each mapped to a user-facing note. No retries yet (Sprint 1).
- Tests: restart test (two turns, rebuild the app on the same `DATA_DIR`, third turn continues); audit trail of the happy path has the expected event types and no secrets; each fault kind ends in a clear note.
- Contract changes folded into `docs/spec.md`.

## Your track (Cursor)
1. Add `react-router-dom` v6 (why: L3 §3.2). Routes: `/` (chat), `/inquiry/verify`, `/inquiry/status/:reference`, `/dev/inbox` (only when `VITE_DEV_TOOLS=1`).
2. `/inquiry/verify`: calls the verify endpoint; success shows "Email verified" and **Continue your inquiry** (calls resume, opens the chat hydrated with messages, cards and draft); errors `token_expired` (offer resend), `token_used`, `email_changed`.
3. `/dev/inbox`: lists outbox messages per recipient, newest first, with clickable links; a Clear button.
4. `/inquiry/status/:reference`: stages, current owner role, last change; works without a chat session.
5. Verification card: countdown on Resend buttons from `resend_available_at`; keep the demo button behind `EMAIL_LINK_DEMO`.
6. Success card links to the tracking page.
7. Prompt: teach `resend_throttled` and the repeat-submit note.
8. Playwright `@scripted` story **S1** (L3 §3.13): verify by opening the link from `/dev/inbox`; submission email in the inbox; status page shows "submitted, waiting for review". Turn on `DEV_TOOLS=true` and `VITE_DEV_TOOLS=1` in the e2e web servers.

## Tests
- Vitest for the three new pages and the countdown.
- Story S1 on desktop and mobile.
- Existing `@scripted` suites still green.

## End-of-day demo check
- [ ] Inquiry → verification email in `/dev/inbox` → click → verified → continue in the chat → SMS code from the inbox → documents → submit → submission email → status page.
- [ ] Pressing Submit twice gives one reference.
- [ ] Restarting the backend in the middle of an inquiry loses nothing: the chat carries on.
- [ ] `GET /api/dev/audit/<id>` shows the inquiry's steps in order, with no OTP, token or raw email in it.
- [ ] `docs/STATUS.md` §0 Day 2 ✅; rows 18, 19, 20 🟡.
