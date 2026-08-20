from typing import Optional
from repository import analytics_repository
from domain.analytics import AnalyticsResponse


def get_analytics_dashboard(
    start_date: str,
    end_date: str,
    location_id: Optional[int] = None
) -> AnalyticsResponse:
    """대시보드 통계 요약, 탐지 추이, 폐기물 분포, 위치 좌표 목록을 통합 조회합니다."""
    summary = analytics_repository.get_analytics_summary(start_date, end_date, location_id)
    trends = analytics_repository.get_daily_trends(start_date, end_date, location_id)
    distribution = analytics_repository.get_waste_distribution(start_date, end_date, location_id)
    locations = analytics_repository.get_analytics_locations(start_date, end_date, location_id)

    return AnalyticsResponse(
        summary=summary,
        trends=trends,
        distribution=distribution,
        locations=locations
    )

def get_regions():
    return analytics_repository.get_all_regions()