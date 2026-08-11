from pydantic import BaseModel, Field

from domain.analytics import AnalyticsSummary, DailyTrend, WasteDistribution


class AnalyticsInsightRequest(BaseModel):
    startDate: str
    endDate: str
    locationId: int | None = None
    summary: AnalyticsSummary
    trends: list[DailyTrend] = Field(default_factory=list)
    distribution: list[WasteDistribution] = Field(default_factory=list)


class AnalyticsInsightResponse(BaseModel):
    title: str
    description: str
