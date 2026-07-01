"""Aggregate router for all v1 API endpoints."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router

v1_router = APIRouter()
v1_router.include_router(auth_router)

__all__ = ["v1_router"]
