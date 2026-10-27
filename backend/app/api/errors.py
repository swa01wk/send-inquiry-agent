"""HTTP error helpers and exception handlers."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.schemas import ErrorBody, ErrorEnvelope
from app.gateway import GatewayError
from app.services.errors import ReferenceNotFoundError
from app.sessions import SessionNotFound, TurnInProgress

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Raise from routers for a spec-shaped error response."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorEnvelope(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(GatewayError)
    async def _gateway_error(_request: Request, exc: GatewayError) -> JSONResponse:
        return error_response(
            503,
            f"{exc.service}_{exc.kind}",
            "A connected system didn't answer. Nothing was lost; please try again shortly.",
        )

    @app.exception_handler(TurnInProgress)
    async def _turn_in_progress(_request: Request, _exc: TurnInProgress) -> JSONResponse:
        return error_response(
            409,
            "turn_in_progress",
            "Please wait for the assistant to finish before sending another message.",
        )

    @app.exception_handler(SessionNotFound)
    async def _session_not_found(_request: Request, _exc: SessionNotFound) -> JSONResponse:
        return error_response(
            404,
            "session_not_found",
            "This chat has expired. Start a new inquiry to continue.",
        )

    @app.exception_handler(ReferenceNotFoundError)
    async def _reference_not_found(
        _request: Request,
        _exc: ReferenceNotFoundError,
    ) -> JSONResponse:
        return error_response(
            404,
            "reference_not_found",
            "We couldn't find an inquiry with that reference number.",
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return error_response(
            400,
            "invalid_request",
            "Something in the request wasn't valid. Please check and try again.",
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
        return error_response(
            429,
            "rate_limited",
            "You're sending messages a little fast. Give it a moment and try again.",
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return error_response(
            500,
            "internal_error",
            "Sorry, something went wrong on our side. Please try again.",
        )
