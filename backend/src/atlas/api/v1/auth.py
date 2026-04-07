"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from atlas.api.deps import get_auth_service
from atlas.schemas.auth import SignInRequest, SignInResponse
from atlas.services.auth import AuthService

router = APIRouter(prefix="/auth")


@router.post("/sign-in", response_model=SignInResponse)
async def sign_in(
    payload: SignInRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> SignInResponse:
    """Authenticate a user by email and password."""
    user = await auth_service.authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return SignInResponse(email=user.email, message="Sign in successful.")
