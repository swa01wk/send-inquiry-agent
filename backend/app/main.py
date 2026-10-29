"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from slowapi.middleware import SlowAPIMiddleware

from app.agent.case_graph import build_case_graph
from app.agent.graph import build_assisted_graph, build_graph
from app.agent.model import ScriptedChatModel, get_chat_model
from app.agent.reviewer_graph import build_reviewer_graph
from app.agent.runtime import AgentRuntime
from app.api.callcentre import router as callcentre_router
from app.api.cases import router as cases_router
from app.api.chat import router as chat_router
from app.api.dev import router as dev_router
from app.api.documents import router as documents_router
from app.api.errors import register_exception_handlers
from app.api.inquiries import router as inquiries_router
from app.api.limiter import limiter
from app.api.master import router as master_router
from app.api.review import router as review_router
from app.api.sessions import router as sessions_router
from app.api.tenant import router as tenant_router
from app.api.verifications import router as verifications_router
from app.config import Settings, get_settings
from app.domain.master import configure_master_data, load_master_data
from app.policy.config import PolicyError, install_policy, load_policy
from app.proactive.engine import tick
from app.services.container import build_services
from app.sessions import SessionStore

logger = logging.getLogger(__name__)

# What `POST /api/dev/reset` deletes under DATA_DIR (every folder the app writes).
DEMO_DATA_DIRS = ("sessions", "cases", "audit", "mock_world", "proactive")


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
    if cfg.reviewer_console and cfg.integrations != "mock":
        msg = "REVIEWER_CONSOLE=true is only allowed with INTEGRATIONS=mock (it's a dev tool)."
        raise RuntimeError(msg)
    if (cfg.callcentre_console or cfg.tenant_portal) and cfg.integrations != "mock":
        msg = (
            "CALLCENTRE_CONSOLE and TENANT_PORTAL are only allowed with INTEGRATIONS=mock "
            "(they stand in for the Tenant Admin Platform and Tenant Central)."
        )
        raise RuntimeError(msg)
    if cfg.dev_tools and cfg.integrations != "mock":
        msg = "DEV_TOOLS=true is only allowed with INTEGRATIONS=mock (the outbox is dev data)."
        raise RuntimeError(msg)

    def default_model_factory() -> BaseChatModel:
        if cfg.agent_mode == "scripted":
            return ScriptedChatModel(steps=[])
        return get_chat_model()

    chat_model_factory = model_factory or default_model_factory

    def init_state(app: FastAPI) -> None:
        """Sessions, services and graphs (start-up, and again after a demo reset)."""
        app.state.settings = cfg
        app.state.policy = policy
        app.state.session_store = SessionStore(
            ttl_minutes=cfg.session_ttl_minutes, data_dir=cfg.data_dir
        )
        app.state.services = build_services(cfg)
        app.state.graph = build_graph(model_factory=chat_model_factory)
        app.state.case_graph = build_case_graph(model_factory=chat_model_factory)
        app.state.reviewer_graph = build_reviewer_graph(model_factory=chat_model_factory)
        app.state.assisted_graph = build_assisted_graph(model_factory=chat_model_factory)

    async def reset_demo() -> None:
        """Delete every demo record (dev tools only) and rebuild the state from scratch."""
        if cfg.data_dir:
            for name in DEMO_DATA_DIRS:
                shutil.rmtree(Path(cfg.data_dir) / name, ignore_errors=True)
        uploads = Path(cfg.upload_dir)
        if uploads.exists():
            for child in uploads.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
        init_state(app)
        logger.info("demo reset")

    async def proactive_loop() -> None:
        """The periodic tick (L5 §3.1): triggers fire without anyone pressing a button."""
        while True:
            await asyncio.sleep(cfg.proactive_tick_seconds)
            try:
                await tick(
                    AgentRuntime(
                        services=app.state.services, master=load_master_data(), settings=cfg
                    )
                )
            except Exception:  # one bad tick mustn't stop the loop
                logger.exception("proactive tick failed")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_state(app)
        task = asyncio.create_task(proactive_loop()) if cfg.proactive_enabled else None
        yield
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Send Inquiry Agent", lifespan=lifespan)
    app.state.reset_demo = reset_demo

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
    app.include_router(cases_router)
    if cfg.reviewer_console:
        app.include_router(review_router)
    if cfg.callcentre_console:
        app.include_router(callcentre_router)
    if cfg.tenant_portal:
        app.include_router(tenant_router)
    if cfg.dev_tools:
        app.include_router(dev_router)

    return app


app = create_app()
