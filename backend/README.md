# Send Inquiry Agent — Backend

FastAPI backend for the Send Inquiry Agent POC.

## Local development

```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Copy `.env.example` to `.env`. For OpenAI, set `OPENAI_API_KEY` and `OPENAI_MODEL` (or `LLM_MODEL`).
For Azure OpenAI, set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `LLM_MODEL` (deployment name).
