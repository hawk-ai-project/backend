# backend/service/climate_analytics_service.py

from typing import Optional, List
from repository import climate_analytics_repository
from domain.climate_analytics import ClimateAnalyticsResponse, ClimateRegion


def get_climate_dashboard(
    start_date: str,
    end_date: str,
    location_id: Optional[int] = None,
    season: Optional[str] = "ALL",
    weather_event: Optional[str] = "ALL",
) -> ClimateAnalyticsResponse:
    summary = climate_analytics_repository.get_climate_summary(
        start_date=start_date,
        end_date=end_date,
        location_id=location_id,
        season=season,
        weather_event=weather_event,
    )
    trends = climate_analytics_repository.get_climate_trends(
        start_date=start_date,
        end_date=end_date,
        location_id=location_id,
        season=season,
        weather_event=weather_event,
    )
    distribution = climate_analytics_repository.get_climate_waste_distribution(
        start_date=start_date,
        end_date=end_date,
        location_id=location_id,
        season=season,
        weather_event=weather_event,
    )
    locations = climate_analytics_repository.get_climate_locations(
        start_date=start_date,
        end_date=end_date,
        season=season,
        weather_event=weather_event,
    )

    return ClimateAnalyticsResponse(
        summary=summary,
        trends=trends,
        distribution=distribution,
        locations=locations,
    )


def get_climate_regions() -> List[ClimateRegion]:
    return climate_analytics_repository.get_climate_regions()
