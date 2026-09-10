"""Account quotas shared across workers. Charge before spending provider quota.

Streaming usage is unavailable: deliberately charge UTF-8 prompt bytes + output
cap, with framing allowance. These are conservative budget units, not billing
measurements. Failed/cancelled calls stay charged because they may cost tokens.
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


def charge(account: str, kind: str, amount: int, limit: int, seconds: int):
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
        if account is not None:
            units = (
                len(system.encode("utf-8"))
                + sum(len(m.content.encode("utf-8")) + 32 for m in messages)
                + max_tokens
                + 256
            )
            charge(account, "tokens", units, settings.account_daily_token_budget, 86400)
        async for delta in self.inner.stream_chat(
            system=system,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield delta
