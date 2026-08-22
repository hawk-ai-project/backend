"""Request and response models for user authentication."""

from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("올바른 이메일 형식을 입력해 주세요.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    profileFileId: int | None = None
    profileImageUrl: str | None = None


class AuthResponse(BaseModel):
    accessToken: str
    refreshToken: str | None = None
    tokenType: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class ProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    currentPassword: str | None = Field(default=None, max_length=128)
    newPassword: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_profile_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("올바른 이메일 형식을 입력해 주세요.")
        return value
