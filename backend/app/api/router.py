from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes import dashboard, jobs

api_router = APIRouter(prefix="/api")

api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(jobs.router, tags=["jobs"])
