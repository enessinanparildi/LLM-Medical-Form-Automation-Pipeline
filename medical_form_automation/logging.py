"""structlog configuration for the application.

PHI policy: never log extracted field values, raw demographics, lab text,
or SOAP notes. Log keys, counts, durations, error types — never patient data.
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

import structlog

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_request_id,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _add_request_id(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    rid = _request_id_var.get()
    if rid != "-":
        event_dict.setdefault("request_id", rid)
    return event_dict


def new_request_id() -> str:
    rid = uuid4().hex
    _request_id_var.set(rid)
    return rid


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
