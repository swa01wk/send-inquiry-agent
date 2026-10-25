# Step 19 — Email-link verification, resume and resend limits

Read first: @docs/specs/l3-reliable-intake.md (sections 3.2, 3.3) @backend/app/services/email_verification.py @frontend/src/components/cards/VerificationCard.tsx

**Start in plan mode:** show the token format, the new endpoints, and the frontend routes and polling. Wait for approval before writing code.

## Goal
The emailed link really verifies the email and brings the user back to the same inquiry, on any device.

## Build
**Backend**
1. `app/auth/tokens.py`: signed JWT (HS256, `RESUME_TOKEN_SECRET`).
   - Purposes: `verify_email`, `resume`, `track`.
   - Claims: inquiry id, email (for `verify_email`), nonce, expiry.
   - Nonces are single-use (stored on the inquiry).
2. `send_verification` emails the `/inquiry/verify?t=…` link built from `PUBLIC_BASE_URL`. The mock keeps exposing a demo token behind `EMAIL_LINK_DEMO`.
3. `POST /api/verifications/email {token}`:
   - validates purpose, expiry, nonce, and that the email still matches the draft;
   - sets `email_verified`;
   - audits the result.

   Errors: `token_expired` (offer resend), `token_used`, `email_changed`.
4. `POST /api/sessions/resume {token}` (purpose `resume` or `verify_email`) opens a new session on the same inquiry and returns:
   - the last 20 chat messages from the checkpoint;
   - the live cards;
   - the draft summary.
5. Actions:
   - `verification_refreshed` runs a turn with the current verification note;
   - `continue_later` emails a resume link.
6. Resend limits from the policy:
   - cooldown and hourly cap per channel;
   - `resend_available_at` on the verification card;
   - note `resend_throttled <s>`.

**Frontend**
1. Route `/inquiry/verify`:
   - calls the verify endpoint;
   - shows success or a friendly error with Resend;
   - a **Continue your inquiry** button calls resume and opens the chat.
2. The verification card:
   - shows countdowns on the resend buttons;
   - has a **Continue later** link;
   - while email is pending, polls `GET /api/sessions/{id}/draft` every 5 s for up to 15 minutes, and sends `verification_refreshed` once `checks.email_verified` turns true.
3. On load with a resume response, the chat store hydrates messages, cards and draft.

## Tests
- **Tokens:** single use; expired; wrong purpose; email changed after sending.
- **Resume:** a second session on the same inquiry sees the same draft and cards, and its next turn continues the history.
- **Throttling:** a resend inside the cooldown is refused and the card shows the wait.
- **Frontend:** polling stops on verify, timeout and unmount; the verify page handles each error code.

## Acceptance criteria
- Gate E3 passes, including a manual check on a second device.
- The `EMAIL_LINK_DEMO` button still works for demos.

## Verify
```
make test && make lint
```
