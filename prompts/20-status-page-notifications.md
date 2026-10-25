# Step 20 — Submission notifications and status page

Read first: @docs/specs/l3-reliable-intake.md (section 3.4) @backend/app/api/inquiries.py @frontend/src/components/cards/SuccessCard.tsx

## Goal
After submitting, the applicant receives the reference and a private tracking link, and the link shows where the inquiry is.

## Build
1. On the `submitted` transition:
   - `NotificationService.send_submission` emails the reference and tracking link, and texts them to a verified mobile;
   - a send failure is retried through the gateway and audited, and never rolls back the submission.
2. Tracking URL: `/inquiry/status/<reference>?t=<token>`, with token purpose `track` and no expiry beyond the inquiry's retention. The success card's `tracking_url` uses it.
3. `GET /api/inquiries/{reference}?t=` requires the token; an unknown reference or bad token returns 404 with no data.
4. The status response adds the current stage, the next owner as a role, and the last change date. With the mock status service, stages come from the inquiry's workflow state.
5. Frontend route `/inquiry/status/:reference`:
   - shows the stages from the response;
   - works without a chat session;
   - is accessible and responsive like the rest of the app.

## Tests
- **Token rules:** missing, wrong reference, and tampered token all return 404.
- **Notifications:** submit sends exactly one notification per channel; a failed send is retried and audited.
- **Frontend:** the status page renders each stage state.

## Acceptance criteria
- No status data is reachable with the reference alone.
- The success card links to the new page.

## Verify
```
make test && make lint
```
