"""Operator dashboard: what the process has seen, and what the budget has left.

Admin-gated, because it shows every account's usage. `ADMIN_ACCOUNTS` lists the
account ids allowed in; with it empty the dashboard is closed to everyone rather
than open to everyone, which is the right way round for a page like this.

Server-rendered so it needs no build step and no frontend change: one URL an
operator can open on a phone at 3am.

It cannot tell you the application is down — a page served by the app is proof
the app is up. Downtime needs a check from outside; see `deploy/watchdog.sh`.
"""

from __future__ import annotations

import html
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.routes.health import _erroring
from app.core.alerts import _deliver
from app.core.alerts import enabled as alerts_enabled
from app.core.config import settings
from app.core.observability import health
from app.db.models import UsageBucket, User

router = APIRouter(prefix="/admin", tags=["admin"])

DAY_SECONDS = 86400


def _require_admin(user: CurrentUser) -> User:
    if not settings.admin_accounts or user.id not in settings.admin_accounts:
        # 404, not 403: an operator page should not confirm its own existence.
        raise HTTPException(status_code=404, detail="Not found")
    return user


def _usage_today(db) -> list[dict]:
    """Per-account token spend in the current UTC day window."""
    window = int(time.time()) // DAY_SECONDS
    rows = db.execute(
        select(UsageBucket.account, UsageBucket.amount)
        .where(UsageBucket.kind == "tokens", UsageBucket.window == window)
        .order_by(UsageBucket.amount.desc())
    ).all()
    budget = settings.account_daily_token_budget
    names = dict(db.execute(select(User.id, User.display_name)).all())
    return [
        {
            "account": names.get(account, account),
            "used": amount,
            "budget": budget,
            "percent": round(100 * amount / budget, 1) if budget else 0.0,
        }
        for account, amount in rows
    ]


@router.get("/metrics")
def metrics(user: CurrentUser, db: DbSession) -> dict:
    """The dashboard's data, for anyone who would rather poll JSON."""
    _require_admin(user)
    accounts = _usage_today(db)
    return {
        **health.snapshot(),
        "environment": settings.environment,
        "alerts_configured": alerts_enabled(),
        "accounts_today": accounts,
        "tokens_today": sum(a["used"] for a in accounts),
    }


@router.post("/test-alert")
async def test_alert(user: CurrentUser) -> dict:
    """Send a real alert down the configured channels.

    Worth doing on the day you set it up. An alerting path nobody has ever
    exercised is a guess, and the day you find out is the day it mattered.
    """
    _require_admin(user)
    if not alerts_enabled():
        raise HTTPException(status_code=400, detail="No alert channel is configured")
    if not await _deliver("Modeer test alert: the configured endpoint accepted this test."):
        raise HTTPException(status_code=502, detail="No alert channel accepted the test")
    return {"sent": True}


def _bar(percent: float) -> str:
    filled = min(int(percent / 5), 20)
    return "█" * filled + "░" * (20 - filled)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(user: CurrentUser, db: DbSession) -> HTMLResponse:
    _require_admin(user)
    snapshot = health.snapshot()
    accounts = _usage_today(db)
    provider = snapshot["provider"]
    last_error = snapshot["last_error"]

    degraded = _erroring(snapshot)
    status_text = "DEGRADED" if degraded else "OK"
    status_class = "bad" if degraded else "good"

    def esc(value) -> str:
        return html.escape(str(value))

    account_rows = (
        "".join(
            f"<tr><td>{esc(a['account'])}</td>"
            f"<td class='num'>{a['used']:,}</td>"
            f"<td class='num'>{a['budget']:,}</td>"
            f"<td class='bar'>{_bar(a['percent'])} {a['percent']}%</td></tr>"
            for a in accounts
        )
        or "<tr><td colspan='4' class='muted'>No usage recorded today.</td></tr>"
    )

    status_rows = (
        "".join(
            f"<tr><td>{esc(k)}</td><td class='num'>{v:,}</td></tr>"
            for k, v in snapshot["by_status_class"].items()
        )
        or "<tr><td colspan='2' class='muted'>No requests yet.</td></tr>"
    )

    error_block = (
        f"<p><b>Latest incident</b> <code>{esc(last_error['incident'])}</code> "
        f"({esc(last_error['type'])}) at {esc(last_error['at'])}<br>"
        f"<span class='muted'>Find it: "
        f"<code>docker compose logs backend | grep incident={esc(last_error['incident'])}</code>"
        f"</span></p>"
        if last_error
        else "<p class='muted'>No unhandled errors since start.</p>"
    )

    quota_block = (
        "<p class='bad'>Provider quota currently blocks: "
        + esc(", ".join(provider["blocked_models"]))
        + ".</p>"
        if provider["blocked_models"]
        else "<p class='muted'>No active provider quota block recorded.</p>"
    )

    alert_block = (
        "<span class='good'>configured</span>"
        if alerts_enabled()
        else "<span class='bad'>NOT configured — you will not be told about anything</span>"
    )

    return HTMLResponse(f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Modeer operations</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.6 system-ui, sans-serif; margin: 0; padding: 24px 16px 64px;
         max-width: 900px; margin-inline: auto; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .08em;
        margin: 32px 0 8px; opacity: .65; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 7px 10px 7px 0; border-bottom: 1px solid #8883; }}
  th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; opacity: .6; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .bar {{ font-family: ui-monospace, monospace; white-space: nowrap; }}
  .good {{ color: #1a7f4b; }} .bad {{ color: #b3261e; }}
  .muted {{ opacity: .6; }}
  code {{ font-family: ui-monospace, monospace; font-size: .9em; }}
  .pill {{ display: inline-block; padding: 2px 10px; border: 1px solid currentColor;
           border-radius: 999px; font-size: 12px; font-weight: 600; }}
  @media (prefers-color-scheme: dark) {{ .good {{ color: #6ee7a8; }} .bad {{ color: #ff9d95; }} }}
</style>
<h1>Modeer operations <span class="pill {status_class}">{status_text}</span></h1>
<p class="muted">{esc(settings.environment)} · up {snapshot["uptime_seconds"]:,.0f}s ·
since {esc(snapshot["started_at"])} · alerts {alert_block}</p>

<h2>Requests</h2>
<table><tr><th>Status</th><th class="num">Count</th></tr>{status_rows}
<tr><td><b>Total</b></td><td class="num"><b>{snapshot["requests"]:,}</b></td></tr></table>

<h2>Errors</h2>
<p>Unhandled since start: <b class="{"bad" if snapshot["unhandled_errors"] else "good"}">
{snapshot["unhandled_errors"]}</b></p>
{error_block}

<h2>AI provider</h2>
<p>Rate limits hit: <b>{provider["rate_limits"]}</b>
{f'· last retry-after {provider["last_retry_after_seconds"]:.0f}s'
 if provider["last_retry_after_seconds"] else ''}</p>
{quota_block}

<h2>Account usage today (UTC)</h2>
<table><tr><th>Account</th><th class="num">Used</th><th class="num">Budget</th>
<th>Share</th></tr>{account_rows}</table>

<h2>Notes</h2>
<p class="muted">Counters reset when the process restarts — a restart is itself
worth noticing. This page cannot tell you the app is down: it is served by the
app. Downtime needs a check from outside.</p>
""")
