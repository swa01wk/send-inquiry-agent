# Step 22 — Evidence for derived values, acceptance stories, KPI report and the L3 gate

Read first: @docs/specs/l3-reliable-intake.md (sections 2, 3.9, 3.13, 6) @backend/scripts/eval_live.py @docs/eval-notes.md @e2e/

## Goal
Make inferred values visibly grounded, prove the whole intake flow with the acceptance stories, measure the L3 KPIs, and run the exit gate.

## Build
1. Evidence for derived values (Should):
   - `update_draft` entries with `source: derived` accept optional `evidence` (≤ 80 chars of the user's words);
   - the confirm card shows "from: '…'";
   - the evidence is stored in the `field_written` audit event;
   - the prompt asks for evidence on every derived value.
2. Acceptance stories S1–S8 (spec §3.13): make sure each exists as a Playwright `@scripted` test (earlier steps added most of them) and add any missing ones. Group them in `e2e/tests/stories/`.
3. `scripts/kpi_report.py`:
   - computes the spec §6 KPIs from audit events for a set of inquiries (an eval run, or a time window);
   - outputs a Markdown table, segmented by scenario and language.
4. Add the KPI report to the end of `eval_live.py` runs.
5. Run the exit gate:
   - every E1–E9 criterion;
   - two live eval runs;
   - the KPI report.

   Record results and any waived Should items in `docs/eval-notes.md`, and the gate result in `docs/STATUS.md`.
6. Fold any remaining L3 contract changes into `docs/spec.md` (spec §4 table) and update `docs/assumptions.md` with the L3 assumptions (spec §7) and whatever Cenomi has confirmed.

## Acceptance criteria
- Every exit-gate row has a passing test or a recorded result.
- `docs/spec.md` matches the code.
- `docs/STATUS.md` shows L3 gate passed (or lists what's waived and why).

## Verify
```
make test && make lint && make e2e && cd backend && uv run python scripts/eval_live.py && uv run python scripts/kpi_report.py --last-run
```
