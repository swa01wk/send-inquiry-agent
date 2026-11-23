# 18 Nov demo days (B1–B5)

These are the day prompts for the feedback from the 18 Nov demo. They run the same way the flow v2 days did ([`prompts/flow-v2/README.md`](../flow-v2/README.md)).

- **Spec:** [`docs/specs/demo-18nov-feedback.md`](../../docs/specs/demo-18nov-feedback.md), gate rows NG1–NG19, decisions M27–M35.
- **Tests:** [`docs/testing/demo-18nov-test-plan.md`](../../docs/testing/demo-18nov-test-plan.md).
- **Catalogue:** [`docs/flow-v2/scenarios.json`](../../docs/flow-v2/scenarios.json), new entries NV01–NV11.
- **Tracker:** [18 Nov demo tracker](https://claude.ai/artifact/4KmQbw2D1bwVzw7TGKTnJd) (milestones MS6–MS15).

| Day | Date | Prompt | Changes | Milestones | Stories that turn green |
| --- | --- | --- | --- | --- | --- |
| B0 | Mon 23 – Tue 24 Nov | — (docs and CI PRs #114, #115, this PR) | Spec, decisions, CI suites, test plan, these prompts | MS1, MS2 | — |
| B1 | Wed 25 Nov | [day-b1-intake-buttons-and-voice.md](day-b1-intake-buttons-and-voice.md) | N1–N7, N13 | MS6, MS7 | NV01, NV02 |
| B2 | Thu 26 Nov | [day-b2-verification.md](day-b2-verification.md) | N8, N9 | MS8, MS9 | NV03–NV05 |
| B3 | Fri 27 Nov | [day-b3-property-details.md](day-b3-property-details.md) | N10, N11, N12 | MS10, MS11 | NV06, NV07 |
| B4 | Mon 30 Nov – Tue 1 Dec | [day-b4-track-and-case-page.md](day-b4-track-and-case-page.md) | N14–N18, X4 | MS12, MS13 | NV08–NV10 |
| B5 | Wed 2 – Thu 3 Dec | [day-b5-console-and-full-run.md](day-b5-console-and-full-run.md) | N19; full scripted, live and demo runs | MS14, MS15 | NV11; all |

Weekends are off. Gate and demo to Muzammil: Fri 4 Dec (MS16).

## Who does what each day

1. **Backend PR (Claude).** Swaroop says "Start MS6" (or MS8, MS10, MS12, MS14) in the project chat. Claude opens one PR from `main`. It holds:
   - policy, master data, domain, services, workflow, API;
   - the screens that don't depend on the model's wording (reviewer console, `/dev`);
   - backend and security tests;
   - the day's catalogue entries, scripted-model scripts and Playwright stories;
   - the eval scenarios and their checks (`scripts/eval_live.py`, `app/agent/eval_checks.py`), unit-tested on scripted turns;
   - the e2e helpers the day needs, and fixes to older stories the backend change breaks;
   - `docs/spec.md` for the day's contract rows (spec §7).

   CI runs `ci.yml`. Claude's workspace can't run browsers or the live model, so Swaroop runs `make e2e-nov18` and `make e2e-int` before merging.
2. **Agent and chat (Swaroop, in Cursor).** Once the backend PR merges, rebase on `main` and run the day's prompt. It covers:
   - the system and case prompts;
   - guard copy;
   - chat cards and pages, with their Vitest and `@fe` tests and screenshots;
   - goldens;
   - live evals (the day's groups, then the full regression) and tuning.
3. **End-of-day check.** Run the checklist at the end of the prompt.
4. **Tracking.**
   - Each PR updates its row in `docs/STATUS.md`.
   - Set the N, NG and MS Status dropdowns in the tracker, and the PR number.

Every PR branches from `main`, so nothing is stacked. Each PR's Testing section lists what ran on each layer (test plan §8).

## Rules for every day

- The golden rules in `.cursor/rules/project.mdc` apply, with ADR-R1–R7, ADR-V1–V6 and ADR-N1–N6 (spec §4).
- **Buttons carry values; code picks the options** (ADR-N1, N2). The model proposes candidates and never writes a value a button sets.
- **No code, link or token in the chat** (ADR-N3, invariant I10).
- **A test a change breaks is fixed in the same PR.** That includes stories and goldens that clicked "Looks right" or the demo link.
- **Each prompt change runs the full `eval-live` regression**, not only the day's group. No group may fall below its last result in `docs/eval-notes.md` beyond `EVAL_TOLERANCE`.
- A scenario changes in the catalogue first, then everywhere that reads it (ADR-V6).
