"""Aggregates the v1 routers; `app.main` mounts this once under `/api/v1`."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    admin,
    admin_definitions,
    applications,
    cabinet,
    content,
    copilot,
    definitions,
    integrations,
    intake,
    services,
)

api_router = APIRouter()
api_router.include_router(services.router)
api_router.include_router(applications.router)
api_router.include_router(cabinet.router)
api_router.include_router(integrations.router)
api_router.include_router(admin.router)
api_router.include_router(definitions.router)
api_router.include_router(admin_definitions.router)
api_router.include_router(intake.router)
api_router.include_router(content.router)
api_router.include_router(copilot.router)
