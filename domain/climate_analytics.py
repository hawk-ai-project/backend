# backend/domain/climate_analytics.py

from pydantic import BaseModel
from typing import List, Optional


class ClimateTopWaste(BaseModel):
    name: str
    count: int
    ratio: float


class ClimateSummary(BaseModel):
    totalInspections: int
    dailyAvgInspections: float
    totalDetections: int
    resolutionRate: float
    resolvedCount: int
    topDetectedItem: ClimateTopWaste


# 👈 [수정] rawDate와 rainfall 필드 선언 추가
class ClimateTrend(BaseModel):
    date: str
    count: int
    rawDate: Optional[str] = None
    rainfall: float = 0.0


class ClimateWasteDistribution(BaseModel):
    name: str
    count: int
    percentage: float


class ClimateLocation(BaseModel):
    id: Optional[int] = None
    region: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: float
    longitude: float
    date: Optional[str] = None
    count: int
    detectionCount: int


class ClimateRegion(BaseModel):
    id: int
    name: str


class ClimateAnalyticsResponse(BaseModel):
    summary: ClimateSummary
    trends: List[ClimateTrend]
    distribution: List[ClimateWasteDistribution]
    locations: List[ClimateLocation] = []
