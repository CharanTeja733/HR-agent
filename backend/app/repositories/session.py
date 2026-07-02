"""Repository for session persistence operations."""

from datetime import timezone
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Session
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    """Data-access layer for the ``sessions`` table."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Session, db)

    async def get_active_by_user(self, user_id: UUID) -> list[Session]:
        """Return all active sessions for a user, most recent first."""
        result = await self.db.execute(
            select(Session)
            .where(Session.user_id == user_id, Session.is_active == True)  # noqa: E712
            .order_by(Session.last_active.desc())
        )
        return list(result.scalars().all())

    async def create_session(
        self, user_id: UUID, device_info: dict | None = None
    ) -> Session:
        """Create a new session for the user.

        ``created_at``, ``last_active`` and ``expires_at`` are set by the
        database via server-side defaults.
        """
        return await self.create(user_id=user_id, device_info=device_info)

    async def update_last_active(self, session_id: UUID) -> None:
        """Touch the ``last_active`` timestamp without a full commit."""
        await self.db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(last_active=func.now())
        )
        await self.db.flush()

    async def count_active_sessions(self) -> int:
        """Count sessions that have been active within the last hour."""
        result = await self.db.execute(
            select(func.count(Session.id))
            .where(
                Session.is_active == True,  # noqa: E712
                Session.last_active >= func.now() - text("INTERVAL '1 hour'"),
            )
        )
        return result.scalar_one()
