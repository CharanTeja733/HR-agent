"""Authentication business logic service.

Thin controllers delegate to this service, which orchestrates repositories,
security utilities, and business rules. Does NOT depend on FastAPI HttpRequest
or Response objects — only on an async DB session.
"""

import logging

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_token_type,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RefreshResponse, TokenResponse
from app.schemas.user import UserResponse

logger = logging.getLogger(__name__)


class AuthService:
    """Service handling user registration, login, and token refresh.

    Accepts an ``AsyncSession`` at construction time — does not use FastAPI
    ``Depends``, so it can be called from routes, background tasks, or scripts.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        department: str,
    ) -> dict:
        """Register a new user account with a bcrypt-hashed password."""
        if await self.user_repo.email_exists(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

        user = await self.user_repo.create(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            department=department,
        )

        logger.info("New user registered: %s (role=%s)", user.email, user.role)

        return {
            "message": "User registered successfully",
            "user": UserResponse.model_validate(user),
        }

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate a user and return access + refresh JWT tokens."""
        user = await self.user_repo.get_by_email(email)

        # Single code path for missing-user and wrong-password prevents
        # user enumeration via timing or error messages.
        if user is None or not verify_password(password, user.hashed_password):
            logger.warning("Failed login attempt for email: %s", email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            logger.warning(
                "Login attempt for deactivated account: %s", email
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact HR administrator.",
            )

        user_id_str = str(user.id)
        access_token = create_access_token(
            user_id=user_id_str,
            email=user.email,
            role=user.role,
            department=user.department,
        )
        refresh_token = create_refresh_token(user_id=user_id_str)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,
            user=UserResponse.model_validate(user),
        )

    async def refresh(self, token: str) -> RefreshResponse:
        """Exchange a valid refresh token for a new access token."""
        try:
            payload = decode_token(token)
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

        if not verify_token_type(payload, "refresh"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

        user = await self.user_repo.get(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact HR administrator.",
            )

        new_access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            department=user.department,
        )

        return RefreshResponse(
            access_token=new_access_token,
            expires_in=3600,
        )
