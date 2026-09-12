"""Account quotas shared across workers. Charge before spending provider quota.

Streaming usage is unavailable: deliberately charge UTF-8 prompt bytes + output
cap, with framing allowance. These are conservative budget units, not billing
measurements.

A call the provider refused or failed before sending a single word is refunded:
the person got nothing, and with "Try again" on every failure a handful of
outages would otherwise use up their day. Anything that produced text — even a
reply cut short — stays charged, as does a call the person abandoned, because
the provider may have spent the tokens either way.
"""

import time
from contextvars import ContextVar

from fastapi import Depends, HTTPException
from sqlalchemy import delete, update

from app.core.auth import caller_id
from app.core.config import settings
from app.db.models import UsageBucket
from app.db.session import SessionLocal
from app.llm.base import LLMProvider
from app.llm.openai_compat_provider import ProviderError

account_scope: ContextVar[str | None] = ContextVar("usage_account", default=None)


class BudgetExceeded(ProviderError):
    pass


def refund(account: str, kind: str, amount: int, window: int) -> None:
    """Give back a charge for work the provider never did.

    Aimed at the window the charge landed in, so a refund that crosses midnight
    UTC cannot hand out allowance on the new day.
    """
    with SessionLocal() as db:
        db.execute(
            update(UsageBucket)
            .where(
                UsageBucket.account == account,
                UsageBucket.kind == kind,
                UsageBucket.window == window,
                UsageBucket.amount >= amount,
            )
            .values(amount=UsageBucket.amount - amount)
        )
        db.commit()


def charge(account: str, kind: str, amount: int, limit: int, seconds: int) -> int:
    """Take ``amount`` from the current window, or raise BudgetExceeded.

    Returns the window charged, so a refund can find it.
    """
    now = int(time.time())
    window = now // seconds
    with SessionLocal() as db:
        # Native conflict handling avoids races across processes on both supported DBs.
        if db.bind.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert
        db.execute(
            insert(UsageBucket)
            .values(account=account, kind=kind, window=window, amount=0)
            .on_conflict_do_nothing()
        )
        result = db.execute(
            update(UsageBucket)
            .where(
                UsageBucket.account == account,
                UsageBucket.kind == kind,
                UsageBucket.window == window,
                UsageBucket.amount <= limit - amount,
            )
            .values(amount=UsageBucket.amount + amount)
        )
        if result.rowcount != 1:
            db.rollback()
            message = (
                "You’ve reached your daily AI allowance. Please try again after midnight UTC."
                if kind == "tokens"
                else "You’re sending messages too quickly. Please wait a minute and try again."
            )
            raise BudgetExceeded(message, retry_after=(window + 1) * seconds - now)
        db.execute(
            delete(UsageBucket).where(
                UsageBucket.account == account,
                UsageBucket.kind == kind,
                UsageBucket.window < window - 1,
            )
        )
        db.commit()
    return window


async def limited_caller(user_id=Depends(caller_id)):
    account = user_id or "local-demo"
    try:
        charge(account, "requests", 1, settings.account_requests_per_minute, 60)
    except BudgetExceeded as exc:
        raise HTTPException(
            429, str(exc), headers={"Retry-After": str(int(exc.retry_after))}
        ) from exc
    token = account_scope.set(account)
    try:
        yield user_id
    finally:
        account_scope.reset(token)


class BudgetedProvider(LLMProvider):
    def __init__(self, inner):
        self.inner = inner
        self.name = inner.name

    async def stream_chat(self, *, system, messages, model, temperature, max_tokens):
        account = account_scope.get()
        units = window = 0
        if account is not None:
            units = (
                len(system.encode("utf-8"))
                + sum(len(m.content.encode("utf-8")) + 32 for m in messages)
                + max_tokens
                + 256
            )
            window = charge(account, "tokens", units, settings.account_daily_token_budget, 86400)
        emitted = False
        try:
            async for delta in self.inner.stream_chat(
                system=system,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                emitted = emitted or bool(delta)
                yield delta
        except ProviderError:
            # A refusal or failure before any text: nothing was delivered.
            if account is not None and not emitted:
                refund(account, "tokens", units, window)
            raise
