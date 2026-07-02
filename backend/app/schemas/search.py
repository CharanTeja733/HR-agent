"""Vector search request/response schemas."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_VALID_ACCESS_LEVELS = {"all", "manager", "hr_admin"}


class SearchRequest(BaseModel):
    """Request schema for POST /search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The search query text",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return",
    )
    access_levels: Optional[list[str]] = Field(
        default=None,
        description="Access levels to filter by. Auto-populated from user role if omitted.",
    )
    min_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold (0.0 to 1.0)",
    )

    @field_validator("access_levels")
    @classmethod
    def validate_access_levels(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Ensure every level in the list is a known access level."""
        if v is not None:
            for level in v:
                if level not in _VALID_ACCESS_LEVELS:
                    raise ValueError(
                        f"Invalid access level: '{level}'. "
                        f"Must be one of {_VALID_ACCESS_LEVELS}"
                    )
        return v


class SearchResult(BaseModel):
    """A single ranked search result."""

    chunk_id: UUID
    content: str
    source: str
    page: Optional[int] = None
    section: Optional[str] = None
    score: float
    confidence: str  # "high", "medium", or "low"


class SearchResponse(BaseModel):
    """Response schema for POST /search."""

    query: str
    results: list[SearchResult]
    total_found: int
    search_time_ms: float
    overall_confidence: Optional[str] = None  # "high", "medium", "low", or "no_match"


class SearchHealthResponse(BaseModel):
    """Health check response for GET /search/health."""

    status: str
    vector_index_exists: bool
    total_documents_indexed: int
    embedding_model: str
    embedding_dimensions: int
