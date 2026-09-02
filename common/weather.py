# backend/backfill_weather.py
import os
import requests
from dotenv import load_dotenv
from common.db import execute_query, fetch_query

load_dotenv()

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
ASOS_URL = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"


def determine_weather_event(
    sum_rn: float, max_ws: float, max_ta: float, min_ta: float
) -> tuple[str, str]:
    """(weather_desc, weather_event) 반환"""
    if sum_rn >= 50.0:
        return "집중호우", "HEAVY_RAIN"
    if max_ws >= 14.0 or (max_ws >= 10.0 and sum_rn >= 20.0):
        return "강풍/태풍", "TYPHOON"
    if max_ta >= 33.0:
        return "폭염", "HEAT_WAVE"
    if min_ta <= -12.0:
        return "한파", "COLD_WAVE"
    if sum_rn > 0.0:
        return "비", "NORMAL"
    return "맑음", "NORMAL"


def backfill_inspections_weather():
    # 1. 날씨 정보가 비어 있는(weather IS NULL) 고유 촬영 일자 목록 조회
    rows = fetch_query("""
        SELECT DISTINCT DATE_FORMAT(captured_at, '%Y%m%d') AS dt, DATE(captured_at) AS raw_date
        FROM inspections
        WHERE deleted_at IS NULL AND (weather IS NULL OR weather = '')
    """)

    if not rows:
        print("업데이트할 대상 점검 데이터가 없습니다.")
        return

    dates = [r["dt"] for r in rows if r.get("dt")]
    min_date = min(dates)
    max_date = max(dates)
    print(f"과거 기상 수집 기간: {min_date} ~ {max_date} (총 {len(dates)}개 일자 대상)")

    params = {
        "serviceKey": WEATHER_API_KEY,
        "numOfRows": 999,
        "pageNo": 1,
        "dataType": "JSON",
        "dataCd": "ASOS",
        "dateCd": "DAY",
        "startDt": min_date,
        "endDt": max_date,
        "stnIds": 108,  # 수도권 기준
    }

    res = requests.get(ASOS_URL, params=params, timeout=15)
    if res.status_code != 200:
        print("기상청 API 요청 실패:", res.text)
        return

    items = (
        res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
    )

    # 2. 날짜별 기상 데이터 매핑 및 UPDATE 실행
    update_sql = """
        UPDATE inspections
        SET weather = %s, rainfall = %s, weather_event = %s
        WHERE DATE(captured_at) = %s AND (weather IS NULL OR weather = '')
    """

    count = 0
    for it in items:
        tm_str = it.get("tm")  # 'YYYY-MM-DD'
        sum_rn = float(it["sumRn"]) if it.get("sumRn") else 0.0
        max_ws = float(it["maxWs"]) if it.get("maxWs") else 0.0
        max_ta = float(it["maxTa"]) if it.get("maxTa") else 0.0
        min_ta = float(it["minTa"]) if it.get("minTa") else 0.0

        weather_desc, event = determine_weather_event(sum_rn, max_ws, max_ta, min_ta)

        execute_query(update_sql, (weather_desc, sum_rn, event, tm_str))
        count += 1

    print(f"완료: 기존 점검 데이터의 기상 정보 업데이트가 완료되었습니다.")


if __name__ == "__main__":
    backfill_inspections_weather()
