# Step 00 — Bootstrap the monorepo

Read first: @README.md @docs/spec.md (section 10) @.cursor/rules/project.mdc

## Goal
Create an empty-but-runnable monorepo for the Send Inquiry Agent POC: a FastAPI backend and a Vite React TypeScript frontend, wired together with Docker Compose and a root Makefile.

## Build
1. `backend/` with `uv`:
   - `pyproject.toml` (Python 3.11+) with: fastapi, uvicorn[standard], pydantic>=2, pydantic-settings, sse-starlette, langgraph, langchain-openai, langchain-core, python-multipart, slowapi, email-validator. Dev: pytest, pytest-asyncio, httpx, ruff, mypy.
   - `app/main.py` with an app factory, CORS from `CORS_ORIGINS`, and `GET /api/health` → `{"status":"ok"}`.
   - `app/config.py`: `Settings` (pydantic-settings) with every variable in spec section 10 and their defaults; `OPENAI_API_KEY` and `OPENAI_MODEL` required only when the agent runs (don't crash `health` or tests without them).
   - Empty packages: `app/api`, `app/agent`, `app/domain`, `app/services`, `app/data`; `tests/test_health.py`.
   - `.env.example`.
2. `frontend/` with Vite (React 18 + TypeScript, strict):
   - Dependencies: `@microsoft/fetch-event-source`. Dev: vitest, @testing-library/react, @testing-library/user-event, jsdom, eslint, prettier.
   - Replace the Vite starter with a single "Send an inquiry" heading. Load Google Fonts Albert Sans (400/500/600/700) and Noto Sans Arabic (400/600) in `index.html`.
   - `.env.example` with `VITE_API_BASE=http://localhost:8000` and `VITE_MOCK=0`.
3. Root:
   - `docker-compose.yml`: `backend` (uvicorn, port 8000, reload, reads `backend/.env`) and `frontend` (vite dev, port 5173).
   - `Makefile`: `dev` (compose up), `dev-backend`, `dev-frontend`, `test` (pytest + vitest), `lint` (ruff, mypy, eslint, tsc --noEmit).
   - `.gitignore` already exists; extend it only if needed.
   - Keep `README.md`, `docs/`, `prompts/`, `design/` and `.cursor/` as they are.

## Acceptance criteria
- `make test` passes (health test + one trivial frontend test).
- `make lint` passes.
- `make dev` serves the backend health check at `:8000/api/health` and the frontend at `:5173`.

## Don't
- Don't add other UI or CSS frameworks, ORMs or databases.
- Don't write any feature code yet.

## Verify
```
make test && make lint
curl -s localhost:8000/api/health
```
