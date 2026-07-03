from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="reels-be")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.routers.feed import router as feed_router
    app.include_router(feed_router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app


app = create_app()
