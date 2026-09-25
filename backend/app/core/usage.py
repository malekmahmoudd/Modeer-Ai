"""Account quotas shared across workers. Charge before spending provider quota.

The charge is taken up front from an estimate in tokens: UTF-8 bytes / 3 for
the prompt (real tokenisers average 3.5-4 bytes a token for English, so this
errs high), plus the output cap, plus the hidden reasoning allowance the
provider grants gpt-oss models. When the provider reports what the call really
used, the unused part of the estimate is given back — so the meter tracks real
tokens, and the estimate only has to be safe, not accurate.

A call the provider refused or failed before sending a single word is refunded:
the person got nothing, and with "Try again" on every failure a handful of
outages would otherwise use up their day. Anything that produced text — even a
reply cut short — stays charged, as does a call the person abandoned, because
the provider may have spent the tokens either way.
"""

import time
from contextvars import ContextVar

from fastapi import Depends, HTTPException
from sqlalchemy import delete, select, update

from app.core.auth import caller_id
from app.core.config import settings
from app.db.models import UsageBucket
from app.db.session import SessionLocal
from app.llm.base import LLMProvider, StreamEnded
from app.llm.openai_compat_provider import ProviderError, reasoning_allowance, usage_sink

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


#: What a typical turn costs after the true-up: a ~2.5k-token prompt, history, a
#: reply, and sometimes the memory call. Only used to turn tokens into "about N
#: messages", which is all a person needs to know.
TYPICAL_TURN_TOKENS = 4000


def allowance(account: str) -> dict:
    """How much of today's allowance this account has left."""
    now = int(time.time())
    window = now // 86400
    with SessionLocal() as db:
        used = db.scalar(
            select(UsageBucket.amount).where(
                UsageBucket.account == account,
                UsageBucket.kind == "tokens",
                UsageBucket.window == window,
            )
        )
    limit = settings.account_daily_token_budget
    used = int(used or 0)
    remaining = max(0, limit - used)
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "messages_left": remaining // TYPICAL_TURN_TOKENS,
        "resets_at": (window + 1) * 86400,
    }


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


def estimate_tokens(*, system, messages, model, max_tokens) -> int:
    """The up-front charge for one call, in tokens. Deliberately high."""
    prompt_bytes = len(system.encode("utf-8")) + sum(
        len(m.content.encode("utf-8")) for m in messages
    )
    return (
        -(-prompt_bytes // 3)  # ceiling division
        + 8 * len(messages)
        + 16
        + max_tokens
        + reasoning_allowance(model)
    )


class BudgetedProvider(LLMProvider):
    def __init__(self, inner):
        self.inner = inner
        self.name = inner.name

    async def stream_chat(self, *, system, messages, model, temperature, max_tokens):
        account = account_scope.get()
        units = window = 0
        if account is not None:
            units = estimate_tokens(
                system=system, messages=messages, model=model, max_tokens=max_tokens
            )
            window = charge(account, "tokens", units, settings.account_daily_token_budget, 86400)
        # The provider writes the usage it reports into this, when it reports any.
        sink: dict = {}
        usage_sink.set(sink)
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
        except StreamEnded:
            if account is not None:
                _true_up(account, units, window, sink)
            raise
        if account is not None:
            _true_up(account, units, window, sink)


def _true_up(account: str, units: int, window: int, sink: dict) -> None:
    """Give back what the estimate over-charged, once the provider says what it used."""
    used = sink.get("total_tokens")
    if isinstance(used, int) and 0 <= used < units:
        refund(account, "tokens", units - used, window)
