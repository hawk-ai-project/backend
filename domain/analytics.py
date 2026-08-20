from pydantic import BaseModel, Field
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


class LocationItem(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: float
    longitude: float
    count: Optional[int] = 0


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    trends: List[DailyTrend]
    distribution: List[WasteDistribution]
    locations: List[LocationItem] = []


class RegionResponse(BaseModel):
    id: int
    name: str