"""FastAPI app factory + middleware."""

import time
from typing import Any, Awaitable, Callable

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from medical_form_automation import __version__
from medical_form_automation.api.routes import router
from medical_form_automation.config import get_settings
from medical_form_automation.logging import (
    configure_logging,
    get_logger,
    new_request_id,
    set_request_id,
)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    log = get_logger("api")
    log.info("app.startup", version=__version__, log_level=settings.log_level)

    app = FastAPI(
        title="Medical Form Automation API",
        version=__version__,
        description="Three-stage pipeline: extract schema, extract answers, populate PDF.",
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> Any:
        rid = request.headers.get("x-request-id") or new_request_id()
        set_request_id(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)

        started = time.perf_counter()
        log.info("request.start", method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - started) * 1000)
            log.exception(
                "request.error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "request.end",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["x-request-id"] = rid
        structlog.contextvars.clear_contextvars()
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        rid = request.headers.get("x-request-id", "-")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        rid = request.headers.get("x-request-id", "-")
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "request_id": rid},
        )

    app.include_router(router)
    return app


# Module-level lazy app for `uvicorn medical_form_automation.api.main:app`.
# Lazy so importing this module without env vars (e.g. during test collection) doesn't crash.
_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)
