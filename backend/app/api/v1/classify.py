"""Classification endpoint — thin route handler.

POST /classify requires JWT authentication.
Useful for testing and debugging the classifier behavior.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.core.deps import get_current_user
from app.models import User
from app.schemas.classify import ClassifyRequest, ClassifyResponse
from app.services.classifier import ClassifierService
from app.services.gemini import GeminiService

router = APIRouter(prefix="/classify", tags=["Classification"])


@router.post("/", response_model=ClassifyResponse)
async def classify_message(
    request: ClassifyRequest,
    current_user: User = Depends(get_current_user),
):
    """Classify a user message for testing and debugging purposes.

    Returns the classification, confidence, and recommended action.
    This endpoint is useful for verifying the classifier behavior.
    """
    try:
        gemini_service = GeminiService(settings.GEMINI_API_KEY)
        classifier = ClassifierService(gemini_service)

        result = await classifier.classify(
            message=request.message,
            conversation_history=[
                msg.model_dump() for msg in request.conversation_history
            ]
            if request.conversation_history
            else None,
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(e)}",
        )
