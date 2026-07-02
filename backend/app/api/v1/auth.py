"""Authentication routes — thin layer over AuthService.

Route handlers are deliberately thin: parse request → call service → return
HTTP response. No business logic lives here.
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_token
from app.database import get_db
from app.models import User
from app.schemas.auth import RefreshResponse, TokenResponse, UserLogin, UserRegister
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user account with a bcrypt-hashed password."""
    service = AuthService(db)
    return await service.register(
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        role=data.role,
        department=data.department,
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post("/login")
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a user and return access + refresh JWT tokens."""
    service = AuthService(db)
    return await service.login(email=data.email, password=data.password)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the current authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post("/refresh")
async def refresh(
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a new access token."""
    service = AuthService(db)
    return await service.refresh(token)
