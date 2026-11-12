# Flow v2 Day F5 (Wed 18 Nov): full Playwright and eval run, demo script, docs

Read first: @docs/specs/flow-v2-alignment.md (§2 all rows) @docs/testing/flow-v2-test-plan.md (§6–§8) @docs/flow-v2/scenarios.json @docs/demo-script.md @docs/POC-LIFECYCLE.md

## Goal
Every scenario proved on every layer, the demo script on the new flow, and the docs matching what's built. The M0 gate is proposed for Thu 19 Nov.

## Backend PR (Claude)
- Fixes from the full runs (each one a test first).
- `docs/POC-LIFECYCLE.md`:
  - §2 redrawn to the v2 flow: public, call centre and signed-in paths; first level; second level with Approve Lead? → contacts → Approve Lead;
  - the `FlowNode` table;
  - the states, including `pending` and `lead_approved`.
- `docs/STATUS.md`: Flow v2 rows, the test-layer table and the gate results.
- `docs/demo-script.md` and `docs/demo-queries.md`:
  - turn by turn on the new order;
  - one public path (Skip → Office → two malls);
  - one registered CR;
  - the second level with forecasted sales and contacts;
  - CC1.
- `demo.spec.ts` follows it.
- The scenario page ([Prospective Tenant Journey v2](https://claude.ai/artifact/Kkt57H5ZLgu2mBbG7nZRi6)) refreshed if any path changed during the build. The catalogue and the page must match.

## Your track (Cursor and your Mac)
1. **INT, all 27, both devices:** `make e2e-int ARGS='--grep @flow-v2'`. Record pass counts per project in the PR.
2. **Regression:** `make e2e-int` (everything) and `make e2e-fe`.
3. **AGENT-LIVE:** `make eval-live GROUP=flow_v2` today and tomorrow morning (27/27 at 3/3 both times), then `make eval-live` for every group (within `EVAL_TOLERANCE`). Rows in `docs/eval-notes.md`.
4. **E2E-LIVE:** `make e2e-live ARGS='--grep @flow-v2'` twice: at least 22/24 plus CC1–CC3. `e2e/results/live-flow-v2-<date>.json`.
5. **Tuning:** any live failure → prompt or guard fix with a scripted reproduction in the catalogue runner first.
6. **Rehearsal:** `make demo`, walk the demo script from `/dev`, desktop and mobile.

## End-of-day check (the gate)
- [ ] FV1–FV22 each green with its test named in the PR.
- [ ] INT 27/27 on desktop Chrome and mobile WebKit.
- [ ] `flow_v2` 27/27 at 3/3 on two runs; other groups within tolerance.
- [ ] E2E-LIVE ≥ 22/24 + CC1–CC3, twice.
- [ ] Demo script rehearsed end to end on Postgres (`make e2e-demo` green).
- [ ] `docs/POC-LIFECYCLE.md`, `docs/STATUS.md`, `docs/spec.md` match the build.
- [ ] Tracker: every V, E and S row Done; F5 Done.
