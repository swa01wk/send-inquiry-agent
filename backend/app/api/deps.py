"""FastAPI dependencies."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from app.config import Settings
from app.domain.master import MasterData, load_master_data
from app.services.container import ServiceContainer
from app.sessions import SessionStore


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_session_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.session_store)


def get_services(request: Request) -> ServiceContainer:
    return cast(ServiceContainer, request.app.state.services)


def get_master_data() -> MasterData:
    return load_master_data()
