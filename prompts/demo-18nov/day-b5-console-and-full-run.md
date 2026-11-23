# 18 Nov Day B5 (Wed 2 – Thu 3 Dec): console buttons, the full run and the demo

Read first: @docs/specs/demo-18nov-feedback.md (§2 rows NG15, NG18, NG19; §3.9; §5.3) @docs/testing/demo-18nov-test-plan.md (§5 NV11, §6 regression, §7, §8 B5) @docs/demo-script.md @docs/scenario-queries.md

## Goal
1. **Console:** Request re-upload sits on each rejected document's row, and the contact details sit inside the Approve Lead action (N19). The console stays internal; this is its only change this round.
2. **Everything passes together:** all scripted stories (old and new), every eval group, the live specs and the QA page.
3. **The 4 Dec demo** runs with only the tenant tab and the Track tab on screen, as Muzammil asked.

## Claude (MS14): merged first
- **Console:**
  - `DocumentDecisions.tsx`: "Request re-upload" with its remarks field on a rejected document's row (test id `doc-request-reupload-<doc_type>`), sending `request_reupload` for that document. The multi-document block in `ActionsPanel.tsx` stays.
  - `ActionsPanel.tsx`: on `lead_approved`, `ContactList` renders inside the Approve Lead action.
  - Vitest.
- **NV11:** catalogue entry and `nv11-console-reupload-on-card.spec.ts`.
- **QA page:** `docs/scenario-queries.md` and `e2e/tests/scenario-queries/` for the new cards, the Track page and case mode (`@qa-scripted`).
- **Demo:**
  - `docs/demo-script.md` for 4 Dec: the tenant tab and the Track tab only; Media or Store intake with option and value buttons; the email confirmed later; Track by reference and email; a re-upload on the action-only case page;
  - `e2e/tests/demo.spec.ts` follows it, reading the outbox through the API;
  - `make e2e-demo` seeds.
- **Docs:** `docs/POC-LIFECYCLE.md` (Track, the email rule, case mode), `docs/STATUS.md`, `docs/eval-notes.md` (the B1–B4 rows Swaroop recorded, plus a summary).

## Your track (Cursor, MS15): the full run
1. **Scripted:** `make e2e-nov18` and `make e2e-int` on desktop and mobile; `make e2e-qa`; `make e2e-demo` twice.
2. **Live:**
   - `make eval-live GROUP=nov18` (every new group 3/3, English and Arabic), then `make eval-live` (all groups within tolerance), on two days if time allows;
   - `make e2e-live` twice.
   - Record both in `docs/eval-notes.md`.
3. **Fixes:** anything the runs find goes to Claude as a short report (story, step, what happened). Prompt wording is yours; code is Claude's.
4. **Rehearsal:** one manual run of `docs/demo-script.md`, about 25 minutes, with `make demo` → `/dev` → Reset demo. Keep `/dev/inbox` in a tab off screen.
5. **Machine check:** the repo isn't on a synced folder; a backup plan if the model is slow (`FORM_MODE=true`).

## End-of-day check
- [ ] Console: reject the Brand Profile → Request re-upload from its row → the case asks for that document only (NV11).
- [ ] NG1–NG19 all pass; tracker NG rows → Done.
- [ ] `docs/eval-notes.md` has the 4 Dec gate run; MS14, MS15 → Done.
- [ ] Muzammil has the confirmations for M29–M31 (MS4), or the demo uses the drafted defaults.
