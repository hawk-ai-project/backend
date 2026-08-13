from fastapi import APIRouter, Query, HTTPException, status
from typing import Optional, List
from service import analytics_service
from domain.analytics import AnalyticsResponse, RegionResponse

import traceback

router = APIRouter(prefix="/api/analytics", tags=["통계 분석"])


@router.get("/summary", response_model=AnalyticsResponse)
def get_analytics_dashboard(
    startDate: str = Query(..., description="조회 시작일 (YYYY-MM-DD)", example="2026-08-01"),
    endDate: str = Query(..., description="조회 종료일 (YYYY-MM-DD)", example="2026-08-10"),
    locationId: Optional[int] = Query(None, description="특정 점검 장소 식별자")
):
    try:
        return analytics_service.get_analytics_dashboard(startDate, endDate, locationId)
    except Exception as e:
        traceback.print_exc()  # 터미널에 상세 에러 위치 및 원인 출력
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통계 데이터 처리 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/regions", response_model=List[RegionResponse])
def get_regions():
    try:
        return analytics_service.get_regions()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"지역 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )