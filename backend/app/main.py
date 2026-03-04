from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.router import api_router
from backend.app.core.config import settings
from backend.app.core.logging import configure_logging
from backend.app.db.models import Base
from backend.app.db.session import SessionLocal, engine
from backend.app.scheduler.scheduler import scheduler_manager
from backend.app.services.config_jobs import sync_jobs_from_config_file

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings.ensure_dirs()

    Base.metadata.create_all(bind=engine)
    log.info("db_ready", extra={"db_path": settings.db_path})

    # Sync jobs from config before scheduler reads DB.
    try:
        with SessionLocal() as db:
            sync_jobs_from_config_file(db, settings.config_path)
    except Exception:
        log.exception("jobs_config_sync_failed", extra={"config_path": settings.config_path})

    await scheduler_manager.start()
    try:
        yield
    finally:
        await scheduler_manager.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(api_router)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir), html=False), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(frontend_dir / "index.html"))


def _main() -> None:
    uvicorn.run(
        "backend.app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,
        access_log=True,
    )


if __name__ == "__main__":
    _main()
