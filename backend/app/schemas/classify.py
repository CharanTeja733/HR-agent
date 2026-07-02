"""Classification request/response schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import VALID_CLASSIFICATIONS


class ConversationMessage(BaseModel):
    """A single message in conversation history."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ClassifyRequest(BaseModel):
    """Request schema for message classification."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user message to classify",
    )
    conversation_history: Optional[list[ConversationMessage]] = Field(
        default=[],
        description="Recent conversation messages for context",
    )


class ClassifyResponse(BaseModel):
    """Response schema for message classification."""

    message: str
    classification: str
    confidence: float
    requires_retrieval: bool
    requires_rewriting: bool
    action: str
    direct_response: Optional[str] = None
    processing_time_ms: float

    @field_validator("classification")
    @classmethod
    def validate_classification(cls, v: str) -> str:
        if v not in VALID_CLASSIFICATIONS:
            raise ValueError(f"Invalid classification: {v}")
        return v
