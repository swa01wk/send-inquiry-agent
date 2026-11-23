# Production image for the hosted POC (deploy/hosted). Local development keeps using
# docker-compose.yml, which mounts the source and runs uvicorn --reload.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data/state /data/uploads \
    && chown -R app /data /app

USER app
EXPOSE 8000

# Migrate, then serve. --proxy-headers so rate limits see the client's IP behind Caddy.
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
