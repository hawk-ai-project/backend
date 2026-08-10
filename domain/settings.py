"""Administrator-managed service settings."""

from pydantic import BaseModel, Field


class ServiceSettings(BaseModel):
    signupEnabled: bool = True
    boardWriteEnabled: bool = True
    inspectionNotificationEnabled: bool = False
    sessionExpireMinutes: int = Field(default=30, ge=5, le=1440)
