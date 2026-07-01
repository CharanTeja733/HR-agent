"""Shared schemas: enums and health check."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class UserRole(str, Enum):
    employee = "employee"
    manager = "manager"
    hr_admin = "hr_admin"


class HealthResponse(BaseModel):
    status: str
    database: str
    gemini_api: str
