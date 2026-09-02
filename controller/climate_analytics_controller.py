# backend/controller/climate_analytics_controller.py

from fastapi import APIRouter, Query, HTTPException, status
from typing import Optional, List
from service import climate_analytics_service
from domain.climate_analytics import ClimateAnalyticsResponse, ClimateRegion

router = APIRouter(prefix="/api/climate-analytics", tags=["기후·계절 통계 분석"])


@router.get("/summary", response_model=ClimateAnalyticsResponse)
def get_climate_dashboard(
    startDate: str = Query(..., description="조회 시작일 (YYYY-MM-DD)"),
    endDate: str = Query(..., description="조회 종료일 (YYYY-MM-DD)"),
    locationId: Optional[int] = Query(None, description="권역/장소 ID"),
    season: Optional[str] = Query(
        "ALL", description="계절 필터 (ALL, SPRING, SUMMER, FALL, WINTER)"
    ),
    weatherEvent: Optional[str] = Query("ALL"),
):
    try:
        return climate_analytics_service.get_climate_dashboard(
            start_date=startDate,
            end_date=endDate,
            location_id=locationId,
            season=season,
            weather_event=weatherEvent,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"기후 통계 처리 중 오류 발생: {str(e)}",
        )


@router.get("/regions", response_model=List[ClimateRegion])
def get_climate_regions():
    try:
        return climate_analytics_service.get_climate_regions()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"권역 목록 조회 중 오류 발생: {str(e)}",
        )
