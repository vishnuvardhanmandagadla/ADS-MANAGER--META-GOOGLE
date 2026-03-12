"""Main API router — assembles all sub-routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from .routes import auth, approvals, clients

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(approvals.router)
