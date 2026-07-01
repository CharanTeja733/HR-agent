"""Session schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    is_active: bool
    created_at: datetime
    last_active: datetime
    expires_at: datetime

    class Config:
        from_attributes = True
