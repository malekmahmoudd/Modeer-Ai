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
import traceback
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.alerts import Severity, notify
from app.core.config import settings

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
    #: Provider throttling. A per-minute 429 is routine; a daily-quota 429 means
    #: the product is down for everyone until the budget refills, which is the
    #: one an operator has to hear about.
    provider_rate_limits: int = 0
    #: Replies delivered truncated because they ran to the token cap.
    length_stops: int = 0
    last_length_stop_model: str | None = None
    provider_quota_exhausted_at: datetime | None = None
    provider_last_retry_after: float | None = None
    provider_failed_until: dict[str, float] = field(default_factory=dict)
    provider_blocked_until: dict[str, float] = field(default_factory=dict)

    def snapshot(self) -> dict:
        uptime = (datetime.now(UTC) - self.started_at).total_seconds()
        return {
            "started_at": self.started_at.isoformat(),
            "uptime_seconds": round(uptime, 1),
            "requests": self.requests,
            "by_status_class": dict(sorted(self.by_status_class.items())),
            "unhandled_errors": self.unhandled_errors,
            "length_stops": self.length_stops,
            "provider": {
                "failed_models": {
                    m: until
                    for m, until in self.provider_failed_until.items()
                    if until > time.time()
                },
                "blocked_models": {
                    m: until
                    for m, until in self.provider_blocked_until.items()
                    if until > time.time()
                },
                "rate_limits": self.provider_rate_limits,
                "quota_exhausted_at": (
                    self.provider_quota_exhausted_at.isoformat()
                    if self.provider_quota_exhausted_at
                    else None
                ),
                "last_retry_after_seconds": self.provider_last_retry_after,
            },
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
    return getattr(route, "path", "<unmatched>")


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.monotonic()
        health.requests += 1
        try:
            response = await call_next(request)
        except Exception as exc:
            # The handler below turns this into a response; here we only need
            # the timing line so a failure is visible in the access log too.
            elapsed = time.monotonic() - started
            logger.warning(
                "%s %s -> unhandled after %.2fs", request.method, _route_template(request), elapsed
            )
            health.by_status_class["5xx"] += 1
            return await unhandled(request, exc)
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

    app.add_exception_handler(Exception, unhandled)
    logging.getLogger("uvicorn.error").addFilter(SafeServerException())


async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    incident = uuid.uuid4().hex[:6]
    health.unhandled_errors += 1
    health.last_error_at = datetime.now(UTC)
    health.last_error_id = incident
    health.last_error_type = type(exc).__name__
    # Render only stack locations; exception text and source lines may contain secrets.
    logger.error(
        "incident=%s %s %s raised %s stack=%s",
        incident,
        request.method,
        _route_template(request),
        type(exc).__name__,
        [(f.filename, f.lineno, f.name) for f in traceback.extract_tb(exc.__traceback__)],
    )
    if health.unhandled_errors % settings.alert_error_threshold == 0:
        notify(
            "Unhandled errors",
            f"{health.unhandled_errors} since start. Latest incident {incident} "
            f"({type(exc).__name__}) on {_route_template(request)}.",
            Severity.CRITICAL,
            key="unhandled-errors",
        )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Something went wrong on our side. Please try again.",
            "incident": incident,
        },
    )


#: A retry-after beyond this is the provider rationing by the day, not the
#: minute. Same threshold the eval harness uses to decide a run cannot finish.
DAILY_QUOTA_RETRY_SECONDS = 180.0


def record_rate_limit(retry_after: float | None, model: str = "unknown") -> None:
    """Note a provider 429, and alert if the daily budget looks spent.

    Called from the provider on every 429. A short retry-after is ordinary
    throttling and only moves a counter; a long one means nobody can use the
    product until the budget refills, and that is worth waking someone for.
    """
    from app.core.alerts import Severity, notify

    health.provider_rate_limits += 1
    health.provider_last_retry_after = retry_after
    if retry_after is not None and retry_after > DAILY_QUOTA_RETRY_SECONDS:
        health.provider_quota_exhausted_at = datetime.now(UTC)
        health.provider_blocked_until[model] = time.time() + retry_after
        notify(
            "AI provider daily quota exhausted",
            f"The provider asked for a {retry_after:.0f}s wait on model {model}. "
            "Replies using that model may fail until its budget refills.",
            Severity.CRITICAL,
            key="provider-quota",
        )


def record_provider_failure(model: str) -> None:
    health.provider_failed_until[model] = time.time() + 120


def record_provider_success(model: str) -> None:
    health.provider_blocked_until.pop(model, None)
    health.provider_failed_until.pop(model, None)


class SafeServerException(logging.Filter):
    """Last-resort ASGI server errors must not format exception values or chains."""

    def filter(self, record):
        if record.exc_info:
            record.msg = "ASGI request failed (%s); see application incident log"
            record.args = (record.exc_info[0].__name__,)
            record.exc_info = None
            record.exc_text = None
        return True


def record_length_stop(model: str) -> None:
    """A reply ran to its token cap and was delivered truncated.

    Not an error — the reader still got the answer — but worth counting. If this
    climbs, the cap is fighting the prompt rather than backing it up, and one of
    the two is wrong.
    """
    health.length_stops += 1
    health.last_length_stop_model = model
