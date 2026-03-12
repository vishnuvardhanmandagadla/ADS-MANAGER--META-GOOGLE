"""Main API router — assembles all sub-routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from .routes import ai, audit, auth, approvals, campaigns, clients, webhooks

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(approvals.router)
api_router.include_router(ai.router)
api_router.include_router(campaigns.router)
api_router.include_router(webhooks.router)
api_router.include_router(audit.router)
