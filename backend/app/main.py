"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from slowapi.middleware import SlowAPIMiddleware

from app.agent.graph import build_graph
from app.agent.model import get_chat_model
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.errors import register_exception_handlers
from app.api.inquiries import router as inquiries_router
from app.api.limiter import limiter
from app.api.master import router as master_router
from app.api.sessions import router as sessions_router
from app.config import Settings, get_settings
from app.services.container import build_services
from app.sessions import SessionStore


def create_app(
    settings: Settings | None = None,
    model_factory: Callable[[], BaseChatModel] | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    chat_model_factory = model_factory or get_chat_model

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = cfg
        app.state.session_store = SessionStore(ttl_minutes=cfg.session_ttl_minutes)
        app.state.services = build_services(cfg)
        app.state.graph = build_graph(model_factory=chat_model_factory)
        yield

    app = FastAPI(title="Send Inquiry Agent", lifespan=lifespan)

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/api/health")
    @limiter.limit(cfg.rate_limit_ip)
    async def health(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.include_router(master_router)
    app.include_router(inquiries_router)

    return app


app = create_app()
