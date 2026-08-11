from pydantic import BaseModel
from typing import List, Optional


class TopDetectedItem(BaseModel):
    name: str
    count: int
    ratio: float


class AnalyticsSummary(BaseModel):
    totalInspections: int
    dailyAvgInspections: float
    totalDetections: int
    resolutionRate: float
    resolvedCount: int
    topDetectedItem: TopDetectedItem


class DailyTrend(BaseModel):
    date: str
    count: int


class WasteDistribution(BaseModel):
    name: str
    count: int
    percentage: float


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    trends: List[DailyTrend]
    distribution: List[WasteDistribution]