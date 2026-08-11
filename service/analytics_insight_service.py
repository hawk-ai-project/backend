from domain.analytics_insight import AnalyticsInsightRequest
from service import analytics_insight_rules


def generate_insight(payload: AnalyticsInsightRequest) -> dict[str, str]:
    return analytics_insight_rules.analyze(payload)
