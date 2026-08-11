from fastapi import APIRouter, Depends

from controller.auth_controller import current_auth
from domain.analytics_insight import AnalyticsInsightRequest, AnalyticsInsightResponse
from service import analytics_insight_service


router = APIRouter(prefix="/api/analytics", tags=["통계 데이터 인사이트"])


@router.post("/insights", response_model=AnalyticsInsightResponse)
def generate_analytics_insight(
    payload: AnalyticsInsightRequest,
    auth=Depends(current_auth),
):
    return analytics_insight_service.generate_insight(payload)
