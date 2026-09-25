from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    admin,
    agents,
    auth,
    briefings,
    chat,
    conversations,
    documents,
    goals,
    health,
    legal,
    memory,
    team,
    tracking,
    users,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(admin.router)
api_router.include_router(health.router)
api_router.include_router(legal.router)
api_router.include_router(users.router)
api_router.include_router(agents.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
api_router.include_router(memory.router)
api_router.include_router(goals.router)
api_router.include_router(briefings.router)
api_router.include_router(tracking.router)
api_router.include_router(documents.router)
api_router.include_router(team.router)

api_router.include_router(auth.router)
