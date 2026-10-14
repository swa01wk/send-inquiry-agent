# Send Inquiry Agent — Backend

FastAPI backend for the Send Inquiry Agent POC.

## Local development

```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` / `OPENAI_MODEL` when running the agent.
