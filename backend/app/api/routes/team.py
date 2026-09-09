"""Ask My Team — explicit, user-controlled multi-specialist consult.

Deliberately minimal and secondary to the core 1:1 chat. The user picks which
specialists to consult; each runs through the same shared runtime with its own
context; Modeer then synthesises. Nothing here is automatic or autonomous.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.agents.registry import get_agent, require_agent
from app.agents.runtime import AgentRuntime
from app.db.models import Conversation
from app.db.session import SessionLocal
from app.llm.base import LLMMessage
from app.llm.provider import get_llm_provider, resolve_model
from app.users.service import get_by_id, get_or_create_demo_user

router = APIRouter(prefix="/team", tags=["team"])


class AskTeamRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    agent_ids: list[str] = Field(min_length=1, max_length=5)


class SpecialistTake(BaseModel):
    agent_id: str
    name: str
    answer: str


class AskTeamResponse(BaseModel):
    question: str
    takes: list[SpecialistTake]
    synthesis: str


@router.post("/ask", response_model=AskTeamResponse)
async def ask_team(
    body: AskTeamRequest,
    x_user_id: Annotated[str | None, Header()] = None,
):
    for slug in body.agent_ids:
        if get_agent(slug) is None:
            raise HTTPException(status_code=404, detail=f"Unknown agent: {slug}")

    db = SessionLocal()
    try:
        user = (
            get_by_id(db, x_user_id) if x_user_id else get_or_create_demo_user(db)
        )
        if user is None:
            raise HTTPException(status_code=404, detail="Unknown user")
        db.commit()

        runtime = AgentRuntime()
        takes: list[SpecialistTake] = []
        for slug in body.agent_ids:
            agent = require_agent(slug)
            convo = Conversation(user_id=user.id, agent_id=slug, title="Ask My Team")
            db.add(convo)
            db.flush()
            answer = ""
            async for event in runtime.run_stream(
                db, user, agent, convo, body.question
            ):
                if event.type == "end":
                    answer = event.data["content"]
                elif event.type == "error":
                    answer = f"(unavailable: {event.data['error']})"
            takes.append(
                SpecialistTake(agent_id=slug, name=agent.name, answer=answer)
            )
        db.commit()

        synthesis = await _synthesise(user, body.question, takes)
        return AskTeamResponse(
            question=body.question, takes=takes, synthesis=synthesis
        )
    finally:
        db.close()


async def _synthesise(user, question: str, takes: list[SpecialistTake]) -> str:
    modeer = require_agent("modeer")
    provider = get_llm_provider()
    joined = "\n\n".join(f"### {t.name}\n{t.answer}" for t in takes)
    system = (
        modeer.system_prompt
        + "\n\n## Ask My Team synthesis\n"
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
