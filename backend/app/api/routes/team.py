"""Ask My Team — explicit, user-controlled multi-specialist consult.

Deliberately minimal and secondary to the core 1:1 chat. The user picks which
specialists to consult; each runs through the same shared runtime with its own
context; Modeer then synthesises. Nothing here is automatic or autonomous.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.agents.registry import get_agent, require_agent
from app.agents.runtime import AgentRuntime
from app.api.deps import refuse_if_suspended
from app.core.auth import session_epoch_matches
from app.core.config import settings
from app.core.usage import BudgetExceeded, limited_caller
from app.db.models import Conversation
from app.db.session import SessionLocal
from app.llm.base import LLMMessage
from app.llm.provider import get_llm_provider, resolve_model
from app.users.service import get_by_id, get_or_create_demo_user

router = APIRouter(prefix="/team", tags=["team"])

CallerId = Annotated[str | None, Depends(limited_caller)]


class AskTeamRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    agent_ids: list[str] = Field(min_length=1, max_length=5)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # Refused before any conversation is created or any provider call made.
        if not value.strip():
            raise ValueError("Question cannot be empty")
        return value


class SpecialistTake(BaseModel):
    agent_id: str
    name: str
    answer: str
    # completed | truncated | interrupted | failed — see app.agents.runtime.
    completion: str = "completed"


class AskTeamResponse(BaseModel):
    question: str
    takes: list[SpecialistTake]
    synthesis: str


@router.post("/ask", response_model=AskTeamResponse)
async def ask_team(
    body: AskTeamRequest,
    x_user_id: CallerId,
    request: Request,
):
    # Checked after authentication, so an anonymous caller still gets 401 and
    # learns nothing about which features this deployment has switched on.
    if not settings.team_enabled:
        raise HTTPException(status_code=404, detail="Ask My Team is not available")
    for slug in body.agent_ids:
        if get_agent(slug) is None:
            raise HTTPException(status_code=404, detail=f"Unknown agent: {slug}")

    db = SessionLocal()
    try:
        user = get_by_id(db, x_user_id) if x_user_id else get_or_create_demo_user(db)
        if user is not None and x_user_id and not session_epoch_matches(request, user):
            raise HTTPException(status_code=401, detail="Please sign in")
        if user is None:
            raise HTTPException(status_code=404, detail="Unknown user")
        refuse_if_suspended(user)
        db.commit()

        runtime = AgentRuntime()
        takes: list[SpecialistTake] = []
        for slug in body.agent_ids:
            agent = require_agent(slug)
            convo = Conversation(user_id=user.id, agent_id=slug, title="Ask My Team")
            db.add(convo)
            db.flush()
            answer, completion = "", "failed"
            # Shared context only: each answer is handed to Modeer for the
            # synthesis, so a specialist's private note used here would reach an
            # agent the Memory page promises it never reaches. And no memory
            # extraction: the same question would otherwise be mined once per
            # specialist.
            turn = runtime.run_stream(
                db, user, agent, convo, body.question, private_notes=False, learn=False
            )
            async for event in turn:
                if event.type == "end":
                    answer, completion = event.data["content"], event.data["completion"]
                elif event.type == "error":
                    if event.data.get("status") == 429:
                        raise HTTPException(429, event.data["error"])
                    answer = f"(unavailable: {event.data['error']})"
            takes.append(
                SpecialistTake(agent_id=slug, name=agent.name, answer=answer, completion=completion)
            )
        db.commit()

        synthesis = await _synthesise(user, body.question, takes)
        return AskTeamResponse(question=body.question, takes=takes, synthesis=synthesis)
    except BudgetExceeded as exc:
        raise HTTPException(
            429, str(exc), headers={"Retry-After": str(int(exc.retry_after))}
        ) from exc
    finally:
        db.close()


async def _synthesise(user, question: str, takes: list[SpecialistTake]) -> str:
    modeer = require_agent("modeer")
    provider = get_llm_provider()
    joined = "\n\n".join(f"### {t.name}\n{t.answer}" for t in takes)
    system = (
        modeer.system_prompt + "\n\n## Ask My Team synthesis\n"
        "Several specialists answered the user's question. Integrate their input "
        "into one coherent recommendation for the user. Note where specialists "
        "agree, flag genuine tension, and end with the concrete next step. Do not "
        "invent specialist opinions that are not present."
    )
    messages = [
        LLMMessage(
            role="user",
            content=f"User question: {question}\n\nSpecialist responses:\n{joined}",
        )
    ]
    result = await provider.complete(
        system=system,
        messages=messages,
        model=resolve_model(modeer.model.model),
        temperature=modeer.model.temperature,
        max_tokens=modeer.model.max_tokens,
    )
    return result.text
