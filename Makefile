# Test layers and their commands: docs/specs/testing-strategy.md §2.
# Every PR: `make ci` locally (CI runs `make ci-remote`: everything except Playwright).
# Gates and demos: `make gate`.

.PHONY: dev demo dev-backend dev-frontend \
	check check-be check-fe lint \
	test test-be test-fe test-agent \
	e2e e2e-int e2e-demo e2e-demo-headed e2e-demo-step e2e-live e2e-report eval-live \
	ci ci-remote gate

SLOW_MO ?= 800
DEMO_PAUSE ?= 2500

# ---- Run ---------------------------------------------------------------

dev:
	docker compose up --build

# Every persona and dev tool on; open http://localhost:5173/dev.
demo:
	docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# ---- BE and FE checks ----------------------------------------------------

# BE: ruff (lint + format) and mypy --strict. `scripts/` joins in step 11d (B1).
check-be:
	cd backend && uv run ruff check app tests && uv run ruff format --check app tests && uv run mypy app

# FE: ESLint, tsc, Prettier.
check-fe:
	cd frontend && npm run lint && npx tsc -b --noEmit && npm run format

check: check-be check-fe

lint: check

# ---- Tests ---------------------------------------------------------------

# BE: the whole pytest suite (includes AGENT-DET).
test-be:
	cd backend && uv run pytest

# FE: Vitest.
test-fe:
	cd frontend && npm test

test: test-be test-fe

# AGENT-DET: tools, guard, actions, bundles and scenario scripts, scripted model only.
# Moves to `pytest -m agent` when step 11d registers the markers (B1).
test-agent:
	cd backend && uv run pytest tests/agent tests/scenarios tests/test_e2e_scripts.py

# Playwright runs locally before every PR (not in CI on PRs; testing strategy §6).
# Deps install only when missing; pass Playwright flags with ARGS, e.g.
#   make e2e-int ARGS='-g "13 wrong files" --project=mobile'
E2E_DEPS = cd e2e && ([ -d node_modules ] || npm ci) && npx playwright install chromium webkit

# INT: Playwright, real frontend + backend, scripted agent (@scripted suites).
e2e-int:
	$(E2E_DEPS) && CI=1 npm run test:scripted -- $(ARGS)

# Full demo-script rehearsal (@demo; desktop only; not part of e2e-int).
e2e-demo:
	$(E2E_DEPS) && CI=1 npm run test:demo -- $(ARGS)

e2e-demo-headed:
	$(E2E_DEPS) && CI=1 E2E_SLOW_MO=$(SLOW_MO) E2E_DEMO_PAUSE_MS=$(DEMO_PAUSE) npm run test:demo -- --headed $(ARGS)

e2e-demo-step:
	$(E2E_DEPS) && CI=1 E2E_SLOW_MO=$(SLOW_MO) E2E_DEMO_PAUSE_MS=$(DEMO_PAUSE) E2E_DEMO_STEP=1 npm run test:demo -- --headed $(ARGS)

e2e: e2e-int

# ---- Live layers (need OPENAI_API_KEY and OPENAI_MODEL) --------------------

# AGENT-LIVE: live evaluation. Groups (GROUP=intake, arabic, …) and repeats arrive in step 11d (B1).
eval-live:
	$(LOAD_ENV); cd backend && GROUP=$(GROUP) uv run python scripts/eval_live.py

# Live targets export backend/.env first, so OPENAI_API_KEY and OPENAI_MODEL reach the
# Playwright process too (the backend reads .env itself; the tests need the key in the shell).
LOAD_ENV = if [ -f backend/.env ]; then set -a; . ./backend/.env; set +a; fi

# E2E-LIVE: Playwright with the real model (@live suites).
e2e-live:
	$(LOAD_ENV); $(E2E_DEPS) && CI=1 E2E_LIVE=1 npm run test:live -- $(ARGS)

e2e-report:
	cd e2e && npx playwright show-report

# ---- Bundles ---------------------------------------------------------------

# Everything a PR needs, run locally. CI runs `check` and `test`; the Playwright part
# (`e2e-int`) is yours to run and report in the PR. `e2e-fe` joins when step 11d adds it (B1).
ci: check test e2e-int

# What CI runs on every PR (no browsers needed).
ci-remote: check test

# Every layer, at gates and before demos.
gate: ci eval-live e2e-live
