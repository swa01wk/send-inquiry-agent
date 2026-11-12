# Flow v2 days (F1–F5)

These are the day prompts for aligning the agent with Cenomi's v2 business flowchart and the 10 Nov demo feedback. They run the same way the re-demo days did ([`prompts/feedback/README.md`](../feedback/README.md)).

- **Spec:** [`docs/specs/flow-v2-alignment.md`](../../docs/specs/flow-v2-alignment.md), gate rows FV1–FV22.
- **Scenarios:** [`docs/flow-v2/scenarios.json`](../../docs/flow-v2/scenarios.json).
- **Tests:** [`docs/testing/flow-v2-test-plan.md`](../../docs/testing/flow-v2-test-plan.md).
- **Tracker:** [Flow v2 build tracker](https://claude.ai/artifact/N6P9iLDCZBniCLoNmXng67).

| Day | Date | Prompt | Changes | Scenarios that turn green |
| --- | --- | --- | --- | --- |
| F0 | Thu 12 Nov | — (docs PR) | Spec, catalogue, test plan, these prompts | — |
| F1 | Fri 13 Nov | [day-f1-names-revoke-console.md](day-f1-names-revoke-console.md) | V4, V5, V8, V9, V14 | S19, S20 |
| F2 | Sat 14 Nov | [day-f2-second-level.md](day-f2-second-level.md) | V6, V7, V11 (console), E4, `FlowNode` | S21–S24 |
| F3 | Mon 16 Nov | [day-f3-public-intake.md](day-f3-public-intake.md) | V1, V2, V10, V11 (intake), V12, V13, E1 | S1–S15, S17 |
| F4 | Tue 17 Nov | [day-f4-call-centre-assistants.md](day-f4-call-centre-assistants.md) | V3, E5, E3, E2 | S16, S18, CC1–CC3 |
| F5 | Wed 18 Nov | [day-f5-full-run.md](day-f5-full-run.md) | Full Playwright, live evals, demo script, docs | All 27 |

Sun 15 Nov is off.

## Who does what each day

1. **Backend PR (Claude).** Swaroop says "Start Day F*n* backend" in the project chat. Claude opens one PR from `main`. It holds:
   - the state machine, effects, services, API, policy and master data;
   - the screens that don't depend on the model's wording: reviewer console, `/dev`, deterministic cards;
   - the backend tests, the catalogue runner entries, the scripted-model scripts and that day's Playwright specs.

   CI runs `ci.yml`. Claude's workspace can't run browsers, so Swaroop runs `make e2e-int` before merging.
2. **Agent and chat (Swaroop, in Cursor).** Once the backend PR merges, rebase on `main` and run the day's prompt. It covers:
   - the system, case and reviewer prompts;
   - agent tools and guard rules that depend on wording;
   - chat cards and their Vitest and `@fe` tests;
   - goldens;
   - live evals and tuning.
3. **End-of-day check.** Run the checklist at the end of the prompt. Where it names a scenario, its `@flow-v2` spec is the check.
4. **Tracking.**
   - Each PR updates its row in `docs/STATUS.md`.
   - When a contract changes, the PR updates `docs/spec.md` (spec §7 says what changes each day).
   - Set the V, E and S Status dropdowns in the tracker.

Every PR branches from `main`, so nothing is stacked. Each PR's Testing section lists what ran on each layer (test plan §8).

## Rules for every day

- The golden rules in `.cursor/rules/project.mdc` apply.
- ADR-R1–R7 (demo feedback) and ADR-V1–V6 (this spec, §4) apply.
- Ids don't change; labels do (ADR-V3).
- The CR never reaches the model (ADR-V4).
- Steps are recorded by code (ADR-V2).
- A scenario changes in the catalogue first, then everywhere that reads it (ADR-V6).
