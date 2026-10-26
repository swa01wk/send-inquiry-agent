# Step 20 — Submission notifications and status page

Read first: @docs/specs/l3-reliable-intake.md (section 3.4) @backend/app/api/inquiries.py @frontend/src/components/cards/SuccessCard.tsx @backend/app/notifications/ (from step 18)

## Goal
After submitting, the applicant receives the reference and a private tracking link, and the link shows where the inquiry is and anything waiting on them.

## Build
1. On the `submitted` transition:
   - `NotificationService.send` with `submission_email` to the verified email, and `submission_sms` to a verified mobile;
   - a send failure is retried through the gateway and audited, and never rolls back the submission.
2. Tracking URL: `/inquiry/status/<reference>?t=<token>`, with token purpose `track` and no expiry beyond the inquiry's retention. The success card's `tracking_url` uses it.
3. `GET /api/inquiries/{reference}?t=` requires the token; an unknown reference or bad token returns 404 with no data.
4. The status response gives the stages, the current stage, the next owner as a role, open requests waiting on the applicant (empty until L4), and the last change date. The mock status service derives them from the inquiry's workflow status. Replace the hard-coded `_STATUS_STEPS` in `api/inquiries.py`.
5. Frontend route `/inquiry/status/:reference`:
   - shows the stages and anything waiting on the applicant;
   - works without a chat session;
   - is accessible and responsive like the rest of the app.
6. Update `docs/spec.md` (REST, success card) and `docs/STATUS.md` (row 20).

## Tests
- **Token rules:** missing, wrong reference, and tampered token all return 404.
- **Notifications:** submit puts exactly one message per channel in the outbox; a failed send is retried and audited.
- **Frontend:** the status page renders each stage state.
- **Playwright:** story S1 (spec §3.13), using `/dev/inbox` for the verification and tracking links.

## Acceptance criteria
- No status data is reachable with the reference alone.
- The success card links to the new page.

## Verify
```
make test && make lint && make e2e
```
