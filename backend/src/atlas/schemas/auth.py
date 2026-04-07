"""Authentication request and response schemas."""

from pydantic import BaseModel, Field, field_validator


EMAIL_SEPARATOR = "@"


class SignInRequest(BaseModel):
    """Request payload for user sign-in."""

    email: str
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Require a basic email shape without extra dependencies."""
        normalized_value = value.strip().lower()
        if EMAIL_SEPARATOR not in normalized_value:
            raise ValueError("Enter a valid email address.")
        return normalized_value


class SignInResponse(BaseModel):
    """Response payload for a successful sign-in."""

    email: str
    message: str
