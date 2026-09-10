"""Know that something is wrong, and be able to find out what.

There is no metrics stack here and no error-tracking service. For a single-host
private deployment that is a reasonable trade, but "no monitoring at all" is
not: an operator needs to be able to answer *is it up*, *is it erroring*, and
*what happened to the request the user is complaining about*.

So this keeps counters in memory and gives every unhandled failure an incident
id that appears both in the log line and in the user's error message. The user
quotes six characters, the operator greps for them.

Deliberately not recorded anywhere: request bodies, replies, memory values, or
anything else the user wrote. Timings, status codes and exception types only.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("modeer.access")

#: A request slower than this is worth a warning on its own line. Chat streams
#: legitimately take seconds; anything past this is usually a stuck provider.
SLOW_REQUEST_SECONDS = 20.0


@dataclass
class Health:
    """Counters since process start. Reset by a restart, which is the point:
    they describe this process, and a restart is itself the event to notice."""

    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    requests: int = 0
    by_status_class: Counter = field(default_factory=Counter)
    unhandled_errors: int = 0
    last_error_at: datetime | None = None
    last_error_id: str | None = None
    last_error_type: str | None = None

    def snapshot(self) -> dict:
        uptime = (datetime.now(UTC) - self.started_at).total_seconds()
        return {
            "started_at": self.started_at.isoformat(),
            "uptime_seconds": round(uptime, 1),
            "requests": self.requests,
            "by_status_class": dict(sorted(self.by_status_class.items())),
            "unhandled_errors": self.unhandled_errors,
            "last_error": (
                {
                    "at": self.last_error_at.isoformat() if self.last_error_at else None,
                    "incident": self.last_error_id,
                    "type": self.last_error_type,
                }
                if self.last_error_id
                else None
            ),
        }


health = Health()


def _route_template(request: Request) -> str:
    """The route pattern, not the filled-in path.

    ``/api/conversations/{conversation_id}`` rather than the real id: the id is
    the user's, and a log full of them is a log full of personal identifiers.
    """
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.monotonic()
        health.requests += 1
        try:
            response = await call_next(request)
        except Exception:
            # The handler below turns this into a response; here we only need
            # the timing line so a failure is visible in the access log too.
            elapsed = time.monotonic() - started
            logger.warning(
                "%s %s -> unhandled after %.2fs", request.method, _route_template(request), elapsed
            )
            raise
        elapsed = time.monotonic() - started
        health.by_status_class[f"{response.status_code // 100}xx"] += 1
        level = logging.WARNING if response.status_code >= 500 else logging.INFO
        if elapsed > SLOW_REQUEST_SECONDS:
            level = max(level, logging.WARNING)
        logger.log(
            level,
            "%s %s %s %.3fs",
            request.method,
            _route_template(request),
            response.status_code,
            elapsed,
        )
        return response


def install(app: FastAPI) -> None:
    """Attach the access log and the unhandled-exception handler."""
    app.add_middleware(AccessLogMiddleware)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        incident = uuid.uuid4().hex[:6]
        health.unhandled_errors += 1
        health.last_error_at = datetime.now(UTC)
        health.last_error_id = incident
        health.last_error_type = type(exc).__name__
        # exc_info gives the traceback; the message carries no request content.
        logger.error(
            "incident=%s %s %s raised %s",
            incident,
            request.method,
            _route_template(request),
            type(exc).__name__,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Something went wrong on our side. Please try again.",
                "incident": incident,
            },
        )
