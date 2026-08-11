from domain.analytics_insight import AnalyticsInsightRequest


def analyze(payload: AnalyticsInsightRequest) -> dict[str, str]:
    summary = payload.summary
    if summary.totalInspections == 0 and summary.totalDetections == 0:
        return {
            "title": "선택한 조건에 분석할 점검 데이터가 없습니다.",
            "description": "조회 기간이나 점검 장소를 변경한 뒤 다시 확인해 주세요.",
        }

    parts = [
        f"조회 기간에는 점검 {summary.totalInspections}건과 폐기물 탐지 {summary.totalDetections}건이 집계되었습니다."
    ]

    top_item = summary.topDetectedItem
    if top_item.count > 0:
        ratio_text = f"{top_item.ratio:.1f}".rstrip("0").rstrip(".")
        parts.append(
            f"가장 많이 탐지된 항목은 {top_item.name}으로 {top_item.count}건, 전체 탐지의 {ratio_text}%입니다."
        )

    if payload.trends:
        peak = max(payload.trends, key=lambda item: item.count)
        if peak.count > 0:
            parts.append(f"일별 탐지는 {peak.date}에 {peak.count}건으로 가장 많았습니다.")

    rate_text = f"{summary.resolutionRate:.1f}".rstrip("0").rstrip(".")
    parts.append(
        f"처리 완료는 {summary.resolvedCount}건이며 현재 처리율은 {rate_text}%입니다."
    )
    if summary.resolutionRate < 50 and summary.totalInspections > 0:
        parts.append("미처리 점검이력을 우선 확인하는 것이 좋습니다.")
    elif top_item.count > 0:
        parts.append(f"{top_item.name} 탐지가 집중된 점검이력을 우선 확인하는 것이 좋습니다.")

    title = (
        f"{top_item.name}이(가) 가장 많이 탐지되었습니다."
        if top_item.count > 0
        else "선택한 기간의 점검 현황을 확인했습니다."
    )
    return {"title": title, "description": " ".join(parts)}
