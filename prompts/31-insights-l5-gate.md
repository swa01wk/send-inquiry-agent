# Step 31 — Process insights, L5 KPIs and the L5 gate

Read first: @docs/specs/l5-governed-proactivity.md (sections 2, 3.2 "Process insight") @backend/scripts/kpi_report.py @docs/eval-notes.md

## Goal
Show whether proactivity helps, and give Cenomi evidence about where the inquiry process loses time.

## Build
1. Insight report (Should): most-requested re-upload documents, rejection reason categories, average time per stage, reminder effectiveness. On demand in the console and monthly as an internal `insight_report` (tier 0).
2. `kpi_report.py` L5 section: proactive items created, accepted, dismissed (with reasons), sent, held; time from reminder to applicant action; stage ages and threshold breaches, with proactivity on and off over the same scripted scenarios.
3. Run the L5 gate: Y1–Y6, a live eval run, the KPI report. Record results in `docs/eval-notes.md` and the gate in `docs/STATUS.md`.
4. Fold remaining L5 contract changes into `docs/spec.md`; add the L5 assumptions to `docs/assumptions.md`.

## Acceptance criteria
- Every L5 gate row has a passing test or a recorded result.
- The KPI report compares proactivity on and off.

## Verify
```
make test && make lint && make e2e && cd backend && uv run python scripts/kpi_report.py --last-run
```
