# Demo feedback days (F1–F5)

These are the day prompts for the client's 3–4 Nov demo feedback. They run the same way the 5-day slice did (`docs/DELIVERY-PLAN.md` Part A and Part C).

The spec is [`docs/specs/demo-feedback.md`](../../docs/specs/demo-feedback.md). Its gate rows are D1–D15.

| Day | Date | Prompt | Packages | Ends with |
| --- | --- | --- | --- | --- |
| F1 | Thu 5 Nov | [day-f1-cr-question-lease-admin.md](day-f1-cr-question-lease-admin.md) | FB1, FB2, FB3 | No CR lookup on the public page; Lease Admin first-level queue; document review service with expiry mock |
| F2 | Fri 6 Nov | [day-f2-document-contact-approval.md](day-f2-document-contact-approval.md) | FB4, FB5 | Per-document approval with expiry; per-contact approval; signatory question |
| F3 | Mon 9 Nov | [day-f3-redemo-hardening.md](day-f3-redemo-hardening.md) | FB6 | Re-demo rehearsal green on Postgres, including a restart |
| — | **Tue 10 Nov** | — | — | **Re-demo with Muzammil** |
| F4 | Wed 11 Nov | [day-f4-type-or-upload.md](day-f4-type-or-upload.md) | FB7 | Type the details or upload the profiles; profile checks |
| F5 | Thu 12 Nov | [day-f5-signed-in-new-brand.md](day-f5-signed-in-new-brand.md) | FB8 | Signed in: company details from Yardi, both profiles, lead codes |

## How a day runs

1. **Backend (Claude).** Swaroop says "Start Day F*n* backend" in the project chat. Claude opens one PR from `main` with the backend work and the screens that don't involve the model (the reviewer console, cards that don't depend on the model's wording, `/dev`). The PR contains the backend tests and the day's Playwright specs. CI runs `ci.yml`, and Swaroop runs `make e2e-int` before merging, because Claude's workspace can't run browsers.
2. **Agent and chat (Swaroop, in Cursor).** Once the backend PR merges, rebase on `main` and run this prompt in Cursor. It covers prompts, agent tools and guards, chat cards, and live evals and tuning.
3. **End-of-day check.** Run the checklist at the end of the prompt. Where it names a Playwright suite, that suite is the check.
4. **Tracking.** Each PR updates its row in `docs/STATUS.md` and, when a contract changes, `docs/spec.md`. Update the Status dropdown in the tracker too.

Every PR branches from `main`, so nothing is stacked. Each PR's Testing section lists what ran on each layer (`docs/specs/testing-strategy.md` §4 and §5).

## Rules for every day

- The golden rules in `.cursor/rules/project.mdc` apply, including golden rule 5 as reworded on 4 Nov: content checks happen only in the document review service.
- The design rules ADR-F1 to ADR-F7 in the spec (§4) apply to every day.
- Parked items stay parked: request access, CR without a login, CR certificate extraction (spec §3.9).
