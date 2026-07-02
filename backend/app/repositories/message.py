"""Repository for message persistence operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Data-access layer for the ``messages`` table."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Message, db)

    async def get_conversation_history(
        self, session_id: UUID, limit: int = 6
    ) -> list[Message]:
        """Return the most recent *limit* messages in chronological order.

        Fetches the last N messages by ``created_at`` descending, then
        reverses the list so callers receive oldest-first ordering.
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def create_message(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        role: str,
        content: str,
        sources: list | None = None,
        confidence: str | None = None,
        tokens_used: int | None = None,
        classification: str | None = None,
    ) -> Message:
        """Create and persist a new message.

        All optional metadata fields are keyword-only so callers can pass only
        what is relevant for the message role.
        """
        return await self.create(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            sources=sources,
            confidence=confidence,
            tokens_used=tokens_used,
            classification=classification,
        )
