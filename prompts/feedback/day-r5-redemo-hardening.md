# Re-demo Day R5 (Mon 9 Nov): hardening and rehearsal

Read first: @docs/specs/demo-feedback.md (§1, §2 rows D10 and D15, §3.6, §5) @docs/demo-script.md @docs/demo-queries.md @e2e/tests/demo.spec.ts @prompts/feedback/day-r4-signed-in-new-brand.md

## Goal
The 10 Nov re-demo shows every feedback point in scope (spec §1). It runs from a clean start on Postgres, survives a backend restart, and opens turn by turn (F5). A Playwright run of the whole script is green the night before.

## Backend PR (Claude): lands first; use it, don't rebuild it
- **Demo stack.** `make demo` runs on Postgres through `docker-compose.demo.yml` (the step 13 store) and applies migrations on start.
- **Seed data.** `scripts/seed_demo.py` seeds three cases:
  - **Case A**, in first review: one expired and one expiring-soon profile, and a mismatch flag;
  - **Case B**, in second review: signatory answered Yes, billing contact waiting for approval;
  - **Case C**, approved and sent to Yardi.
- **Reset.** `POST /api/dev/reset` reseeds. `/dev` lists the three cases, with links for the Lease Admin and RLM personas.
- **Rehearsal spec.** `demo.spec.ts` is rewritten as `Demo script — 10 Nov @demo`, using three browser contexts (applicant, Lease Admin, RLM):
  1. New chat, turn by turn → "Do you have a CR?" → **No** → "I'll upload the profiles" → details filled from the profiles and confirmed → email link and OTP → submit (F1, F5, F6).
  2. Lease Admin: open the case from the "Inquiry for approval" email (F7). Expiry chips → reject the expired profile → request re-upload (F8).
  3. Applicant: case link → re-upload → resubmit.
  4. Lease Admin: approve each document → approve first level (F8, F16).
  5. Applicant: contacts → "Yes, I'm the authorised signatory" → billing contact (F19).
  6. Lease Admin: reject the billing contact → the applicant fixes it → approve (F16).
  7. **Restart the backend** (`docker compose restart backend`, or the restart helper from step 13) and reload every context. Nothing is lost.
  8. RLM: approve → Yardi.
  9. Applicant: tracking page shows the outcome.
  10. A second chat: type a company name, then upload a mismatching profile → one-sentence warning → the flag shows in the Lease Admin's brief (F6).
  11. "Yes, I have a CR" → sign-in → Leasing Opportunities → company from Yardi → new brand → both profiles (F2, F3).
- **Checks along the way.** Each step asserts the audit timeline and the dev outbox (`review_assigned` to the Lease Admin, `reupload_request`, `contacts_request`, `inquiry_accepted`).
- **Make targets.** `make e2e-demo` runs it, `make e2e-demo-headed` shows it, and `make e2e-demo-step` steps through it.

## Your track (Cursor): script, tuning and rehearsal
1. **`docs/demo-script.md`:** rewrite for 10 Nov in the order above, with the feedback number on each beat so Muzammil can tick them off.
   - Open turn by turn: "Hi, I'd like to lease a space" → the CR question → No → brand and space → contact.
   - Move the one-message paste to an optional "power user" beat at the end of intake (I15).
   - Keep the beats Muzammil accepted on 3 Nov (in-chat verification, review card, tracking).
2. **`docs/demo-queries.md`:** the turn-by-turn messages for the new opening, the type-or-upload answers and the signatory answers.
3. **Live tuning:**
   - run `make eval-live` for `intake`, `channels`, `case`, `cr_privacy`, `signatory` and `document_extract`;
   - fix wording in the prompts, not with new guards, unless a safety invariant fails;
   - record the results in `docs/eval-notes.md`.
4. **`make e2e-live`:** one full live run of the self-service, existing-tenant and case personas.
5. **Machine check:**
   - the repo is outside any iCloud-synced folder;
   - a fresh clone runs `make demo`;
   - migrations apply from empty;
   - no stray migration files.
6. **Rehearse once headed** (`make e2e-demo-headed`), then once by hand from `/dev`.

## Tests
- `make ci`.
- `make e2e-demo`, green twice in a row.
- AGENT-LIVE: the six groups above within tolerance of the step 12 baseline. `cr_privacy`, `signatory` and `document_extract` at 3/3.
- E2E-LIVE: the self-service, existing-tenant and case personas pass, with INV8 on.

## End-of-day check (re-demo ready)
- [ ] `make e2e-demo` green on Postgres, including the restart step, twice in a row.
- [ ] Manual run from `/dev`, reset first, takes about 25 minutes and matches `docs/demo-script.md`.
- [ ] Backup: if the model is slow on the day, form mode finishes the intake (story S13 passes).
- [ ] Share the three-lane flow (`docs/POC-LIFECYCLE.md` §2.4) and the updated design doc with Muzammil before the call (F14, F15, I1).
- [ ] `docs/STATUS.md` Re-demo R5 ✅, with gate rows D1–D15 marked; tracker I1, I6, I15 set to Done.
