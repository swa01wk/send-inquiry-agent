.PHONY: dev demo dev-backend dev-frontend test lint e2e e2e-live e2e-report

dev:
	docker compose up --build

demo:
	OTP_MOCK_CODE=1234 VITE_DEMO=1 docker compose up --build

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd backend && uv run ruff check app tests && uv run ruff format --check app tests && uv run mypy app
	cd frontend && npm run lint && npx tsc -b --noEmit

e2e:
	cd e2e && npm ci && npx playwright install chromium webkit && CI=1 npm run test:scripted

e2e-live:
	cd e2e && npm ci && npx playwright install chromium webkit && CI=1 E2E_LIVE=1 npm run test:live

e2e-report:
	cd e2e && npx playwright show-report
