# 18 Nov Day B2 (Thu 26 Nov): a code that expires, and an email that doesn't block

Read first: @docs/specs/demo-18nov-feedback.md (§2 rows NG6, NG7; §3.4 "Code expiry" and "The email doesn't block"; §8 M29, M30) @docs/testing/demo-18nov-test-plan.md (§3 B2, §4, §5 NV03–NV05, §6 `email_pending`) @backend/app/agent/system_prompt_v2.md ("Saving and coming back") @frontend/src/components/cards/VerificationCard.tsx

## Goal
1. **The SMS code expires** after 60 s. The card counts down, says when it has expired and offers Resend (N8, M30).
2. **The email link doesn't hold up the applicant.** Once the mobile is verified, the inquiry is saved and they carry on to Property Details and Submit. The email must be confirmed before the Leasing Admin approves; until then the case says so (N9, M29).
3. **Landline only** works as today: the email link is the only check, so it's needed before Submit.

M29 and M30 are decided (23 Nov). If Muzammil changes them later, it's a policy value (`verification.email_required_before`, `verification.otp_ttl_seconds`), not a code change.

## Backend PR (Claude, MS8): merged first; use it, don't rebuild it
Contracts are folded into @docs/spec.md (rows marked "18 Nov B2").
- **Policy:** `verification.otp_ttl_seconds: 60`, `verification.email_required_before: first_approval` (or `submit`), `verification.email_reminder_hours: 48`.
- **Code expiry:**
  - `MockOtpService` records when each code was sent; `verify` returns `"ok" | "wrong" | "expired"`;
  - `_submit_otp` (`app/agent/actions.py`): `expired` → `[ui_event] otp_expired`, attempts unchanged, card refreshed;
  - verification card `mobile.code_expires_at` (ISO).
- **The email rule:**
  - `app/domain/rules.py: intake_verified(draft)`; `verification_blockers` reads `email_required_before`;
  - the `verification` section is done when `intake_verified`; the pending save uses it (`agent/pending.py`).
- **After submit:**
  - `first_approval_blockers` (`app/workflow/machine.py`) adds `email_unverified` while the case's `draft.email_verified` is false;
  - new case event `contact_email_verified` (actor system, any status before `second_review`) sets it and audits;
  - the email link (`POST /api/verifications/email`) and the resume link apply it when the session has a case;
  - the console shows "Applicant hasn't confirmed their email yet" with the date sent, and a Resend link action;
  - the proactive tick re-sends the link once at `email_reminder_hours`.
- **Status:** `waiting_on_you` includes "Confirm your email" while `email_unverified`.
- **e2e:** steps `dev_clock_advance_seconds`, `resend_code`, `skip_email`. NV03–NV05 catalogue entries, scripts and specs (`nv03-code-expires.spec.ts`, `nv04-email-after-submit.spec.ts`, `nv05-landline-needs-email.spec.ts`). Stories that assumed "nothing is saved until the email is verified" are fixed here.
- **Evals:** group `email_pending` (English and Arabic) with its checks and unit tests.
- **Tests:** the B2 rows in the test plan §3, including `tests/security/test_otp_not_in_model.py`.

## Your track (Cursor, MS9): the agent and the chat
1. **System prompt**, "Saving and coming back" and the verification lines:
   - Once the mobile is verified, the inquiry is saved: "You're verified. We've also emailed you a link to confirm your email; you can do that any time." Say it once, then ask the first Property Details question. Never hold the applicant until the email is done.
   - Never say they can't submit without the email (mobile case). Landline only: the email link is the check; nudge for it before Property Details, as today.
   - On `otp_expired`: "That code has expired. Tap Resend for a new one." Never read out or repeat a code.
2. **`VerificationCard`:**
   - countdown from `mobile.code_expires_at` ("Code expires in 0:42", test id `otp-countdown`);
   - at zero, "Code expired" (`otp-expired`) and Resend (`otp-resend`), disabled during the cooldown;
   - the email row reads "Link sent to … · not confirmed yet" until verified, without blocking anything.
   - Vitest with fake timers; screenshots for running and expired.
3. **Goldens** whose verification wording changes, re-recorded with the reason.
4. **Live evals:** `make eval-live GROUP=email_pending` (3/3, English and Arabic), then the full `make eval-live`.

## Tests
- Vitest and `make e2e-fe` for `VerificationCard`.
- `make e2e-nov18 ARGS='--grep "NV0[345]"'`, then the full `make e2e-int`.
- AGENT-LIVE: `email_pending` at 3/3; every other group within tolerance.

## End-of-day check
- [ ] Code sent → countdown → dev clock +61 s → "Code expired" → the old code is refused → Resend → the new code works (NV03).
- [ ] Mobile verified, email not opened → Property Details → … → Submit → reference. In the console, Approve is refused: "Applicant hasn't confirmed their email yet". Open the link from the outbox → Approve works (NV04).
- [ ] Landline only → Submit stays disabled until the link is opened (NV05).
- [ ] The pending inquiry shows in `GET /api/dev/flow/<session>` right after the SMS code.
- [ ] `docs/STATUS.md` B2 row; tracker N8, N9 → Done; MS8, MS9 → Done.
