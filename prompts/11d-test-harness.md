# Step 11d — Test harness: six layers, CI and the PR template

Read first: @docs/specs/testing-strategy.md @Makefile @e2e/playwright.config.ts @frontend/src/mocks/ @backend/scripts/eval_live.py @.github/workflows/e2e.yml @backend/pyproject.toml

Runs after 11c and before 12. **Start in plan mode:** show the Makefile targets, the frontend Playwright config and scenario mechanism, the catalogue format, the `eval_live.py` changes and the CI jobs. Wait for approval before writing code.

## Goal
Every layer in the testing spec exists, has one command, and runs in CI where the spec says, so every later step can prove itself the same way.

## Build
1. **Makefile** (spec §2): `check-be`, `check-fe`, `check` (with `lint` as an alias), `test-be`, `test-fe`, `test` (unchanged meaning), `e2e-fe`, `e2e-int` (with `e2e` as an alias), `test-agent`, `eval-live` (`GROUP=` optional), `e2e-live`, `ci`, `gate`.
2. **BE** (spec §2.1):
   - ruff and `mypy --strict` over `scripts/` too; fix the existing issues there (including the E501 lines in `generate_e2e_scripts.py`);
   - pytest markers `unit`, `api`, `agent`, `parity`, `contract`, `postgres`, `sandbox`, `live`, registered in `pyproject.toml`; default runs exclude `sandbox` and `live`; tag existing tests;
   - `pytest-cov` (dev dependency) with a report on every run; record today's numbers in `docs/STATUS.md` §7; set the floors from spec §2.1 only where today's numbers already meet them, and list the rest as targets.
3. **FE** (spec §2.2):
   - `VITE_MOCK=1` reads `?scenario=<name>`; today's demo flow becomes the `demo` scenario and the default; scenarios live in `frontend/src/mocks/scenarios/`;
   - `e2e/playwright.fe.config.ts` (frontend web server only, `VITE_MOCK=1`, desktop Chrome and mobile WebKit projects);
   - `e2e/tests/fe/` with `@fe` suites for today's cards (confirm fields, mall picker, verification, documents, review, success, quick replies), the draft panel and stream edge cases (error with Retry, `message_remove`, 409, dropped connection); axe on each; a keyboard-only happy path; card screenshots in CI only.
4. **INT** (spec §2.3): the existing `@scripted` suites unchanged, run by `make e2e-int`; tidy `support/events.ts` so later steps can assert on the outbox and audit endpoints when they arrive.
5. **AGENT-DET** (spec §2.4): `make test-agent` runs `pytest -m agent` (tools, guard, actions, bundles, scenarios); add `tests/agent/test_prompt_snapshot.py` (system message for fixed drafts in each phase, snapshot files committed). Add the `claims_submission` regression cases from #12 if missing.
6. **AGENT-LIVE** (spec §2.5): `eval_live.py` gains scenario groups (today's = `intake`), `EVAL_REPEATS` (3) with the 2-of-3 rule, `EVAL_TOLERANCE`, JSON output to `backend/eval-results/` (gitignored), a Markdown summary, and the safety-invariant checks I1–I7 (spec §3) on every turn as hard failures.
7. **E2E-LIVE** (spec §2.6): add the invariant checks to `e2e/support/turnChecks.ts`; support the `@flaky` tag (reported, excluded from the pass rate); failures attach the SSE capture (as today).
8. **Catalogue** (spec §7): move today's scenario definitions to `backend/tests/scenarios/catalogue/*.yaml`; `generate_e2e_scripts.py` and the scenario tests read from it. No behaviour change: existing scripts must regenerate byte-identical.
9. **CI** (spec §6): `.github/workflows/ci.yml` runs `backend` and `frontend` on every PR (done on Day 1; Playwright runs locally since 27 Oct); add an `eval-live` job to `e2e.yml` (`workflow_dispatch`, nightly when `NIGHTLY_LIVE=true`).
10. **PR template** `.github/pull_request_template.md`: summary, then a **Testing** table with one row per layer (ran / not run / why), the live results when §4 requires them, and a `docs/STATUS.md` checkbox.
11. Fold spec §8 into `docs/spec.md`; update `docs/STATUS.md` (row 11d and §7).

## Tests
**Layers** (`docs/specs/testing-strategy.md`): Builds the layers themselves; see Acceptance criteria.
- Each new Make target runs green locally on a clean checkout.
- `make e2e-fe` passes on desktop and mobile; an axe violation added on purpose fails it (then revert).
- `make test-agent` fails with a readable diff when a prompt sentence changes (then revert).
- `make eval-live GROUP=intake` produces the JSON and summary; a forced invariant breach (a scripted reply claiming submission) fails the run.
- Regenerated e2e scripts are byte-identical.

## Acceptance criteria
- `make ci` is green locally, and `ci.yml` is green.
- `make gate` runs every layer end to end (live layers need `OPENAI_API_KEY` and `OPENAI_MODEL`).
- `docs/STATUS.md` §7 shows every layer with its command and current status.

## Verify
```
make ci && make eval-live GROUP=intake && make e2e-live
```
