"""Aggregates the v1 routers; `app.main` mounts this once under `/api/v1`."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import applications, services

api_router = APIRouter()
api_router.include_router(services.router)
api_router.include_router(applications.router)
