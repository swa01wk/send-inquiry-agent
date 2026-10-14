.PHONY: dev demo dev-backend dev-frontend test lint

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
