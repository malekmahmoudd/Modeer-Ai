from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    meta: dict
    created_at: datetime

    @computed_field
    @property
    def completion(self) -> str:
        """completed | truncated | interrupted | failed. Rows saved before
        statuses existed were only ever saved on success."""
        return self.meta.get("completion", "completed")


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agent_id: str
    title: str
    created_at: datetime
    last_message_at: datetime | None


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = Field(default_factory=list)


class ConversationCreate(BaseModel):
    agent_id: str


class ChatRequest(BaseModel):
    """One chat turn, or ``retry`` to regenerate the latest unfinished reply.

    Validation runs before the route touches the database or the provider, so a
    blank message is refused without creating a conversation or spending quota.
    """

    message: str | None = Field(default=None, max_length=8000)
    conversation_id: str | None = None
    retry: bool = False

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Message cannot be empty")
        return value

    @model_validator(mode="after")
    def _turn_or_retry(self) -> ChatRequest:
        if self.retry:
            if self.message is not None:
                raise ValueError("A retry reuses the original message; do not send a new one")
            if not self.conversation_id:
                raise ValueError("A retry needs the conversation it belongs to")
        elif self.message is None:
            raise ValueError("Message is required")
        return self
