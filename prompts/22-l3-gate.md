# Step 22 — Evidence for derived values, KPI report and the L3 gate

Read first: @docs/specs/l3-reliable-intake.md (sections 2, 3.9, 6) @backend/scripts/eval_live.py @docs/eval-notes.md

## Goal
Make inferred values visibly grounded, measure the L3 KPIs, and run the exit gate.

## Build
1. Evidence for derived values (Should):
   - `update_draft` entries with `source: derived` accept optional `evidence` (≤ 80 chars of the user's words);
   - the confirm card shows "from: '…'";
   - the evidence is stored in the `field_written` audit event;
   - the prompt asks for evidence on every derived value.
2. `scripts/kpi_report.py`:
   - computes the spec §6 KPIs from audit events for a set of inquiries (an eval run, or a time window);
   - outputs a Markdown table, segmented by scenario.
3. Add the KPI report to the end of `eval_live.py` runs.
4. Run the exit gate:
   - every E1–E7 criterion;
   - two live eval runs;
   - the KPI report.

   Record results and any waived Should items in `docs/eval-notes.md` and `docs/specs/README.md`.
5. Fold all L3 contract changes into `docs/spec.md` (spec §4 table) and update `docs/assumptions.md` with whatever Cenomi has confirmed.

## Acceptance criteria
- Every exit-gate row has a passing test or a recorded result.
- `docs/spec.md` matches the code.

## Verify
```
make test && make lint && cd backend && uv run python scripts/eval_live.py && uv run python scripts/kpi_report.py --last-run
```
