# 18 Nov Day B4 (Mon 30 Nov – Tue 1 Dec): Track your inquiry, and an action-only case page

Read first: @docs/specs/demo-18nov-feedback.md (§2 rows NG11–NG14, NG16, NG17; §3.6, §3.7, §3.8; §4 ADR-N3–N5; §8 M33, M35) @docs/testing/demo-18nov-test-plan.md (§3 B4, §4, §5 NV08–NV10, §6 `case_actions`, `track_privacy`) @backend/app/agent/case_prompt.md @frontend/src/pages/CasePage.tsx @frontend/src/pages/InquiryStatusPage.tsx @frontend/src/App.tsx

## Goal
This is Muzammil's main point: a tenant with no login can find their inquiry, see who holds it, and do what's asked of them.
1. **Track your inquiry** at `/inquiry/track`: reference + email, a 6-digit code to the email on file, then the case page. Only the requester gets in, and the page never says whether an inquiry exists (N14, M33).
2. **The status lives on the case page**, as a strip above the chat. It says "With you" whenever something waits on the tenant (N15, N16).
3. **No text box after submit.** Each waiting item has its own buttons: upload or replace, and a comment on that item. With nothing waiting, "Send a follow-up" (N17, M35).
4. **Contacts on cards**, with "Same as primary contact" (N18).
5. **X4:** the General Inquiry agent can use the same Track endpoints and the status endpoint.

If Keerthana's check of the old Track page (T5) has landed, copy its wording; otherwise build to M33 as written.

## Backend PR (Claude, MS12): merged first; use it, don't rebuild it
Contracts are folded into @docs/spec.md (rows marked "18 Nov B4"), including the X4 contract with an example.
- **Track:**
  - `TrackCodeService` (`app/services/track_code.py`, mock): 6 digits, 10 minutes, single use, 3 attempts, stored hashed;
  - `POST /api/inquiries/track {reference, email}` → always `202 {"sent": true}`; a code only when the email matches the case's primary email; rate limits 5/hour per reference, 20/hour per IP;
  - `POST /api/inquiries/track/verify {reference, email, code}` → `{"token"}` (a `track` token) or `400 track_code_invalid` for every failure;
  - template `track_code`; audit `track_code_sent`, `track_code_verified` (reference only, never the code);
  - a verified code applies `contact_email_verified` if the email was still unconfirmed (B2).
- **Status:**
  - `services/status.py: _from_case`: any open request (or an unconfirmed email) → `owner_role: applicant`, `owner_label: "With you"`; otherwise "With the " + `ROLE_LABELS`;
  - `InquiryStatusResponse.owner_label`;
  - `actions.tracking_url` → `/inquiry/case?t=<track token>` (templates `submission_email`, `submission_sms`).
- **Case actions:**
  - action `case_comment {request_id | null, doc_type | null, text}` (≤ 1,000 characters);
  - case event `applicant_comment` (actor applicant, before `sent_to_yardi`, no status change), `Case.comments`;
  - template `applicant_comment` to the case's reviewer; the console timeline and document rows show comments;
  - policy `case.max_follow_ups_per_day: 3`;
  - the model gets `[ui_event] comment_sent <doc_type|follow_up>`, never the text.
- **Contacts:** the contacts card gains `same_as` options (`primary`, `authorized_signatory`) that fill from verified contacts; `update_contacts` is removed from the case agent's tools.
- **Invariant I10** in `app/agent/invariants.py` and `e2e/support/invariants.ts`: no link, SMS code or Track code in replies or cards, and no reply asking for one.
- **e2e:**
  - steps `track`, `track_code`, `case_comment`, `follow_up`, `contacts_same_as_primary`;
  - NV08–NV10 catalogue entries, scripts and specs (`nv08-track-page.spec.ts`, `nv09-reupload-action-only.spec.ts`, `nv10-follow-up-and-contacts.spec.ts`);
  - `support/outbox.ts: trackCode(messages)`;
  - older stories that used `/inquiry/status/` or typed contacts in case mode are fixed here.
- **Evals:** groups `case_actions` and `track_privacy` (English and Arabic) with their checks and unit tests.
- **Tests:** the B4 rows in the test plan §3, including `tests/security/test_track.py`.

## Your track (Cursor, MS13): the pages, the case agent, the chat
1. **`TrackPage`** (`/inquiry/track`, `App.tsx`):
   - reference and email → "If those details match an inquiry, we've sent a 6-digit code to that email." → code → on success `POST /api/cases/open` with the token, then the case page;
   - one error for every failure; no hint whether the reference exists;
   - linked from the public page's footer.
2. **`/inquiry/status/:reference`** redirects to `/inquiry/case?t=…` with the same token (keep the route for old emails).
3. **`CasePage`:**
   - `StatusStrip` above the chat (reference, `owner_label`, waiting items, last update); the stage timeline folds under "Show progress";
   - no `Composer` in case mode;
   - each request card shows its own actions: Upload or Replace per document, "Add a comment" per document (`case_comment`);
   - with nothing waiting, "Send a follow-up" (a small form, `case_comment` with no request);
   - contacts card: "Same as primary contact" and "Same as the signatory" buttons.
4. **Case prompt** (`case_prompt.md`):
   - never invite typing ("type", "reply with", "send me");
   - point to the item's buttons;
   - after `comment_sent`, one line: "Thanks, we've passed that to the team." Never claim the reviewer has read it;
   - with an open request, say it's waiting on them, plainly.
5. **Public chat:** "How do I track my inquiry?" or a pasted reference → point to the Track page in one line; never give a status from a reference alone, never ask for a code in the chat.
6. Vitest, `@fe` specs `track-page`, `case-page`, screenshots.
7. **Live evals:** `make eval-live GROUP=case_actions`, `GROUP=track_privacy` (3/3, English and Arabic), then the full `make eval-live`.

## Tests
- Vitest and `make e2e-fe` for `TrackPage`, `StatusStrip`, `CasePage`.
- `make e2e-nov18 ARGS='--grep "NV(08|09|10)"'`, then the full `make e2e-int`.
- AGENT-LIVE: the two groups at 3/3; every other group within tolerance.

## End-of-day check
- [ ] Track with a wrong email → the same message, no email in the outbox; the right email → code from the outbox → the case page with the strip (NV08).
- [ ] A seeded re-upload case: the strip says "With you"; there's no text box; replace the Brand Profile, comment on it, resubmit; the strip says "With the Leasing Admin"; the comment shows in the console (NV09).
- [ ] Nothing waiting → Send a follow-up → shows in the console. On Approve Lead?: "Yes, it's me" for the signatory, "Same as primary contact" for billing (NV10).
- [ ] The submission email's link opens the case page; an old `/inquiry/status/…` link redirects there.
- [ ] `docs/STATUS.md` B4 row; tracker N14–N18, X4 → Done; MS12, MS13 → Done.
