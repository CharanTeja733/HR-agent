"""Vector search endpoints — thin route handlers.

POST /search requires JWT authentication.
GET /search/health is public.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.search import (
    SearchHealthResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------


def get_search_service(
    db: AsyncSession = Depends(get_db),
) -> SearchService:
    """Create a search service wired with the current DB session and API key."""
    return SearchService(db=db, gemini_api_key=settings.GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search HR documents using semantic (vector) similarity.

    Generates a query embedding via Gemini, then performs cosine
    similarity search against the ``hr_documents`` table with pgvector,
    automatically filtering results by the authenticated user's role.
    """
    try:
        service = SearchService(db, settings.GEMINI_API_KEY)
        result = await service.search(
            query=request.query,
            user_role=current_user.role,
            top_k=request.top_k,
            access_levels=request.access_levels,
            min_score=request.min_score,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.get("/health", response_model=SearchHealthResponse)
async def search_health(
    db: AsyncSession = Depends(get_db),
):
    """Check whether the vector search subsystem is operational.

    Public endpoint — no authentication required.
    """
    service = SearchService(db, settings.GEMINI_API_KEY)
    return await service.health_check()
