"""Administrator-managed AI recommendation schedule."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

ScheduleMode = Literal["DAILY", "INTERVAL"]

class RecommendationScheduleUpdate(BaseModel):
    mode: ScheduleMode = "DAILY"
    dailyTime: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    intervalMinutes: int = Field(default=1440, ge=1, le=10080)

class RecommendationSchedule(RecommendationScheduleUpdate):
    timezone: str = "Asia/Seoul"
    lastRunAt: datetime | None = None
    nextRunAt: datetime
