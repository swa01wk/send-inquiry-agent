"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from slowapi.middleware import SlowAPIMiddleware

from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel, get_chat_model
from app.api.chat import router as chat_router
from app.api.dev import router as dev_router
from app.api.documents import router as documents_router
from app.api.errors import register_exception_handlers
from app.api.inquiries import router as inquiries_router
from app.api.limiter import limiter
from app.api.master import router as master_router
from app.api.sessions import router as sessions_router
from app.api.verifications import router as verifications_router
from app.config import Settings, get_settings
from app.domain.master import configure_master_data, load_master_data
from app.policy.config import PolicyError, install_policy, load_policy
from app.services.container import build_services
from app.sessions import SessionStore


# Registered once at import: a limit decorated inside create_app would be added again for
# every app built (tests build many), and identical limits share one counter.
@limiter.limit(lambda: get_settings().rate_limit_ip)
async def health(request: Request) -> dict[str, str]:
    return {"status": "ok"}


def create_app(
    settings: Settings | None = None,
    model_factory: Callable[[], BaseChatModel] | None = None,
) -> FastAPI:
    get_settings.cache_clear()
    cfg = settings or get_settings()

    # Business rules and master data are loaded once, before anything can serve a
    # request; a bad policy file stops the app here with a readable error.
    policy = load_policy(cfg.policy_path)
    configure_master_data(cfg.master_data_source)
    master = load_master_data()
    unknown_lines = [
        line for line in policy.product_lines if line not in master.ids_for_kind("unit_types")
    ]
    if unknown_lines:
        msg = f"Policy product_lines not in master data unit_types: {', '.join(unknown_lines)}"
        raise PolicyError(msg)
    install_policy(policy)
    if cfg.dev_tools and cfg.integrations != "mock":
        msg = "DEV_TOOLS=true is only allowed with INTEGRATIONS=mock (the outbox is dev data)."
        raise RuntimeError(msg)

    def default_model_factory() -> BaseChatModel:
        if cfg.agent_mode == "scripted":
            return ScriptedChatModel(steps=[])
        return get_chat_model()

    chat_model_factory = model_factory or default_model_factory

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = cfg
        app.state.policy = policy
        app.state.session_store = SessionStore(
            ttl_minutes=cfg.session_ttl_minutes, data_dir=cfg.data_dir
        )
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

    app.add_api_route("/api/health", health, methods=["GET"])

    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.include_router(master_router)
    app.include_router(inquiries_router)
    app.include_router(verifications_router)
    if cfg.dev_tools:
        app.include_router(dev_router)

    return app


app = create_app()
