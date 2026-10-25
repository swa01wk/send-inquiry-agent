# Step 11b — Fix demo-run bugs, then add Playwright e2e tests

> Done (branch `fix/ui-bugs-and-e2e`, ported onto `main` after PR #1). Kept for history; renumbered from 13 so it doesn't clash with `13-durable-state.md`.

Branch: `fix/ui-bugs-and-e2e` (already created from `main`).

Read first: @docs/specs/ui-bugs.md @docs/specs/e2e-playwright.md @docs/spec.md @docs/design-spec.md @.cursor/rules/agent.mdc
Screenshots of the bugs: `docs/specs/screenshots/demo-run-01.png` … `07.png`.

Work in two phases. Commit after each phase.

## Phase A — Fix the bugs (docs/specs/ui-bugs.md)

Fix B1 to B8 exactly as specified, in this order: B1 (PDF upload), B2 (duplicate confirm cards), B3 (bubble formatting), B4 + B5 + B8 (prompt), B6 (CR chip), B7 (phone row).

Rules:
- Fix root causes in the backend first; the frontend safeguard in B2 is extra, not a replacement.
- Keep the parser rule in `guard.py` / `.cursor/rules/agent.mdc`: no heuristic writes `source=user`.
- Update `docs/spec.md` for contract changes: dotted `allowed_extensions`, `QuickReplyOption.action` / `placeholder`.
- After editing `backend/app/agent/system_prompt.md`, copy the static prompt into `docs/agent-system-prompt.md`.
- Add the unit tests listed under each bug's **Acceptance**.

Check:
```bash
make lint && make test
cd backend && uv run python scripts/eval_live.py   # twice; log in docs/eval-notes.md
```
Then a manual browser run with the 8 demo queries plus real PDF uploads. Card states must match the B2 lifecycle table.

Commit: `fix: demo-run UI bugs (PDF upload, duplicate cards, formatting, prompt, lost users, CR chip, phone row)`

## Phase B — Playwright e2e (docs/specs/e2e-playwright.md)

Build sections 1–7 of the spec:
1. `e2e/` package, config with desktop and mobile projects, fixtures, global setup.
2. Backend scripted agent mode (`AGENT_MODE=scripted`, `X-Test-Scenario` header honoured only in that mode), with one JSON script per scenario in `backend/tests/e2e_scripts/`, plus a unit test that validates every script.
3. Page object `e2e/pages/inquiry.ts` and SSE capture behind `VITE_E2E=1`.
4. Plain-language and UI checks in `e2e/support/plainLanguage.ts`, run after every turn; axe scan and mobile overflow check at the end.
5. All 22 scenarios as `@scripted`; the scenarios marked **L** also as `@live`.
6. Live results JSON and the eval-notes row.
7. Makefile targets `e2e`, `e2e-live`, `e2e-report`, and `.github/workflows/e2e.yml`.

Rules:
- Assert on draft state (`GET /api/sessions/{id}/draft`), cards and UI. In `@live`, never assert on exact wording.
- Use accessible locators (`getByRole`, `getByLabel`, `getByText`). Add `data-testid` only where no accessible name exists.
- Wait for each turn's `done`; no fixed `waitForTimeout`.
- No test may depend on another test's state; each opens a fresh session.

Check:
```bash
make e2e          # must pass on desktop-chrome and mobile
make e2e-live     # ≥ 13/14, twice; results in e2e/results and docs/eval-notes.md
make e2e-report   # check traces of any failures
```

To prove the tests guard the fixes, temporarily revert B1 (undotted extensions) and confirm scenario 13 fails, then restore it.

Commit: `test: Playwright e2e suites (scripted + live) for non-technical user scenarios`

## Finish

Push the branch and open a PR to `main`. The PR description lists:
- bugs fixed, with before/after notes;
- e2e results for both projects;
- the two live run summaries;
- anything you changed from the specs, and why.
