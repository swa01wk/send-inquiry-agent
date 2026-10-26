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
- [ ] `docs/STATUS.md` §0 Day 2 ✅; rows 18, 19, 20 🟡.
