# Re-demo days (R1–R5)

These are the day prompts for the client's 3–4 Nov demo feedback. They run the same way the 5-day slice did (`docs/DELIVERY-PLAN.md` Part A and Part C).

The spec is [`docs/specs/demo-feedback.md`](../../docs/specs/demo-feedback.md). Its gate rows are D1–D15.

| Day | Date | Prompt | Feedback (improvements) | Ends with |
| --- | --- | --- | --- | --- |
| R1 | Thu 5 Nov | [day-r1-cr-question-lease-admin.md](day-r1-cr-question-lease-admin.md) | F1, F2 (I2, I3); F7 (I13 light); F8 (I8); F6 (I12 mock) | No CR lookup on the public page; Lease Admin queue and "Inquiry for approval" email; document review service with expiry |
| R2 | Fri 6 Nov | [day-r2-document-contact-approval.md](day-r2-document-contact-approval.md) | F8, F16 (I4, I18, I5); F19 (I16) | Per-document approval with expiry; per-contact approval; signatory question |
| R3 | Sat 7 Nov | [day-r3-type-or-upload.md](day-r3-type-or-upload.md) | F6 (I19) | Type the details or upload the profiles; profile checks |
| R4 | Sun 8 Nov | [day-r4-signed-in-new-brand.md](day-r4-signed-in-new-brand.md) | F3 (I9) | Signed in: company details from Yardi, new brand, both profiles checked |
| R5 | Mon 9 Nov | [day-r5-redemo-hardening.md](day-r5-redemo-hardening.md) | F5 (I15); F14, F15 (I1); demo stability (I6) | Whole re-demo green on Postgres, including a restart |
| — | **Tue 10 Nov** | — | — | **Re-demo with Muzammil** |

**Naming.** F1–F20 are the client's feedback points, I1–I19 the improvements, M1–M12 the client questions (tracker), R1–R5 the build days, and D1–D15 the spec's gate rows. Playwright stories for these days start with `rd-`.

## How a day runs

1. **Backend (Claude).** Swaroop says "Start Day R*n* backend" in the project chat. Claude opens one PR from `main` with the backend work and the screens that don't involve the model (the reviewer console, cards that don't depend on the model's wording, `/dev`). The PR contains the backend tests and the day's Playwright specs. CI runs `ci.yml`, and Swaroop runs `make e2e-int` before merging, because Claude's workspace can't run browsers.
2. **Agent and chat (Swaroop, in Cursor).** Once the backend PR merges, rebase on `main` and run this prompt in Cursor. It covers prompts, agent tools and guards, chat cards, and live evals and tuning.
3. **End-of-day check.** Run the checklist at the end of the prompt. Where it names a Playwright suite, that suite is the check.
4. **Tracking.** Each PR updates its row in `docs/STATUS.md` and, when a contract changes, `docs/spec.md`. Update the Status dropdown in the tracker too.

Every PR branches from `main`, so nothing is stacked. Each PR's Testing section lists what ran on each layer (`docs/specs/testing-strategy.md` §4 and §5).

## Rules for every day

- The golden rules in `.cursor/rules/project.mdc` apply, including golden rule 5 as reworded on 4 Nov: content checks happen only in the document review service.
- The design rules ADR-R1 to ADR-R7 in the spec (§4) apply to every day.
- Parked items stay parked: request access, CR without a login, CR certificate extraction (spec §3.9).
