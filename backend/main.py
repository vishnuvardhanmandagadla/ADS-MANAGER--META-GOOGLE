"""Ads Engine — FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ads_engine.core.config import get_app_config, get_safety_config, get_settings
from ads_engine.approval.policies import ApprovalPolicy
from ads_engine.approval.queue import init_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    settings = get_settings()
    config = get_app_config()
    safety = get_safety_config()

    print(f"[ads-engine] Starting in {settings.app_env} mode")
    print(f"[ads-engine] DB: {settings.database_url}")

    # Phase 3: init approval queue (skip if already initialised by tests)
    from ads_engine.approval import queue as _queue_module
    if _queue_module.approval_queue is None:
        policy = ApprovalPolicy(safety)
        init_queue(policy)
    queue = _queue_module.approval_queue
    pending = queue.pending_count()
    print(f"[ads-engine] Approval queue ready — {pending} pending action(s)")

    # TODO Phase 4: init DB connection pool
    # TODO Phase 5: init AI client
    yield
    print("[ads-engine] Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    config = get_app_config()

    app = FastAPI(
        title=config["app"]["name"],
        version=config["app"]["version"],
        description=config["app"]["description"],
        docs_url=config["api"]["docs_url"] if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS — allow Next.js dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config["api"]["cors_origins"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────────────
    from ads_engine.api.router import api_router
    from ads_engine.api.routes.websocket import router as ws_router
    app.include_router(api_router)
    app.include_router(ws_router)   # /ws — no version prefix for WebSocket

    @app.get("/health")
    async def health():
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
