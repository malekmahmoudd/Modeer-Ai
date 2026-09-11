"""Tell the operator when something is wrong, without a paid service.

Two rules shape everything here.

**An alert must never break the request that triggered it.** Sending is
fire-and-forget and every failure is swallowed after logging: a broken webhook
must not turn a working reply into an error.

**An alert must never carry user content.** Event names, counts and exception
types only. Alerts land in a chat app, which is the least private place a
person's conversation could end up.

Channels are optional and additive — configure either, both, or neither:

    ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...   (Slack, Discord, ntfy)
    ALERT_TELEGRAM_BOT_TOKEN=123:ABC
    ALERT_TELEGRAM_CHAT_ID=456789

With neither set, alerting is off and `notify` returns immediately, so
development and tests stay silent.

What this CANNOT do is tell you the application is down: a process that has
stopped cannot send anything. That needs a check from outside — see
`deploy/watchdog.sh` and the external monitor in `docs/OPERATIONS.md`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

import httpx

from app.core.config import settings

logger = logging.getLogger("modeer.alerts")

#: The same problem usually fires repeatedly. Send once, then stay quiet about
#: that specific event for this long, so a crash loop is one message and not
#: three hundred.
THROTTLE_SECONDS = 900.0
SEND_TIMEOUT_SECONDS = 10.0


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


_ICON = {Severity.INFO: "•", Severity.WARNING: "!", Severity.CRITICAL: "!!"}


@dataclass
class Throttle:
    """Last-sent time per event key. In memory: a restart is itself an event."""

    sent: dict[str, float] = field(default_factory=dict)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        last = self.sent.get(key)
        if last is not None and now - last < THROTTLE_SECONDS:
            return False
        self.sent[key] = now
        return True


throttle = Throttle()


def enabled() -> bool:
    return bool(settings.alert_webhook_url) or bool(
        settings.alert_telegram_bot_token and settings.alert_telegram_chat_id
    )


def _format(event: str, detail: str, severity: Severity) -> str:
    return (
        f"{_ICON[severity]} Modeer [{settings.environment}] {severity.value.upper()}: {event}"
        f"\n{detail}"
    )


async def _post(client: httpx.AsyncClient, url: str, payload: dict) -> bool:
    response = await client.post(url, json=payload, timeout=SEND_TIMEOUT_SECONDS)
    if response.status_code >= 400:
        logger.warning("alert channel returned %s", response.status_code)
    return 200 <= response.status_code < 300


async def _deliver(text: str) -> bool:
    delivered = False
    channels = []
    if settings.alert_webhook_url:
        channels.append((settings.alert_webhook_url, {"content": text, "text": text}))
    if settings.alert_telegram_bot_token and settings.alert_telegram_chat_id:
        channels.append(
            (
                f"https://api.telegram.org/bot{settings.alert_telegram_bot_token}/sendMessage",
                {"chat_id": settings.alert_telegram_chat_id, "text": text},
            )
        )
    async with httpx.AsyncClient() as client:
        for url, payload in channels:
            try:
                accepted = await _post(client, url, payload)
                delivered = accepted or delivered
            except Exception as exc:  # one broken channel must not suppress the other
                logger.warning("alert channel failed: %s", type(exc).__name__)

    return delivered


def notify(
    event: str,
    detail: str = "",
    severity: Severity = Severity.WARNING,
    *,
    key: str | None = None,
) -> None:
    """Send an alert, at most once per throttle window per ``key``.

    Safe to call from anywhere, including an exception handler: it never raises
    and never blocks the caller waiting on the network.
    """
    if not enabled():
        return
    if not throttle.allow(key or event):
        return

    text = _format(event, detail, severity)
    logger.info("alert: %s", event)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Called from synchronous code with no loop (a CLI, a worker). Send
        # inline rather than dropping it; this path is rare.
        try:
            asyncio.run(_deliver(text))
        except Exception:  # noqa: BLE001 - an alert must never raise
            logger.warning("could not deliver alert %s", event)
        return

    task = loop.create_task(_deliver(text))
    _background.add(task)
    task.add_done_callback(_finished)


#: Strong references, or the event loop may garbage-collect a task mid-flight.
_background: set[asyncio.Task] = set()


def _finished(task: asyncio.Task) -> None:
    _background.discard(task)
    if task.cancelled():
        return
    if error := task.exception():
        logger.warning("alert delivery failed: %s", type(error).__name__)
