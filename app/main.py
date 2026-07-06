from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import migrate
    from app.ingest.sources import sync_sources
    from app.ingest.x_accounts import sync_x_accounts
    from app.scheduler import start_scheduler

    migrate()
    sync_sources()
    sync_x_accounts()
    sched = start_scheduler()
    try:
        yield
    finally:
        if sched is not None:
            sched.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="reels-be", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.routers.auth import router as auth_router
    from app.routers.feed import router as feed_router
    from app.routers.sources import router as sources_router
    app.include_router(auth_router)
    app.include_router(feed_router)
    app.include_router(sources_router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app


app = create_app()
