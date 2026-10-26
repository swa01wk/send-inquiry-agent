# Test layers and their commands: docs/specs/testing-strategy.md §2.
# Every PR: `make ci` (also run by .github/workflows/ci.yml). Gates and demos: `make gate`.

.PHONY: dev demo dev-backend dev-frontend \
	check check-be check-fe lint \
	test test-be test-fe test-agent \
	e2e e2e-int e2e-live e2e-report eval-live \
	ci gate

# ---- Run ---------------------------------------------------------------

dev:
	docker compose up --build

demo:
	OTP_MOCK_CODE=1234 VITE_DEMO=1 docker compose up --build

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

# INT: Playwright, real frontend + backend, scripted agent (@scripted suites).
e2e-int:
	cd e2e && npm ci && npx playwright install chromium webkit && CI=1 npm run test:scripted

e2e: e2e-int

# ---- Live layers (need OPENAI_API_KEY and OPENAI_MODEL) --------------------

# AGENT-LIVE: live evaluation. Groups (GROUP=intake, arabic, …) and repeats arrive in step 11d (B1).
eval-live:
	cd backend && GROUP=$(GROUP) uv run python scripts/eval_live.py

# E2E-LIVE: Playwright with the real model (@live suites).
e2e-live:
	cd e2e && npm ci && npx playwright install chromium webkit && CI=1 E2E_LIVE=1 npm run test:live

e2e-report:
	cd e2e && npx playwright show-report

# ---- Bundles ---------------------------------------------------------------

# Everything a PR needs. `e2e-fe` (frontend-only Playwright) joins when step 11d adds it (B1).
ci: check test e2e-int

# Every layer, at gates and before demos.
gate: ci eval-live e2e-live
