# backend/common/weather.py

import os
import math
import requests
from datetime import datetime, timedelta
from urllib.parse import unquote
from dotenv import load_dotenv
from common.db import execute_query, fetch_query

# ==============================================================================
# 1. 환경 변수 및 외부 연동 상수 설정
# ==============================================================================

load_dotenv()

# 공공데이터포털 인증키 (requests 호출 시 내부 이중 인코딩 방지를 위해 unquote 처리)
RAW_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_API_KEY = unquote(RAW_KEY)

# 기상청 공공데이터 API 엔드포인트
ASOS_URL = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
ULTRA_SRT_NCST_URL = (
    "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
)

# 권역 접두사별 기상청 지상(종관)기상관측(ASOS) 대표 관측소 지점 코드 (stnId) 매핑
REGION_STATION_MAP = {
    "서울": 108,
    "수도": 108,
    "경기": 119,  # 수원 관측소
    "인천": 112,
    "부산": 159,
    "대구": 143,
    "대전": 133,
    "광주": 156,
    "울산": 152,
    "강원": 105,  # 강릉 관측소
}


# ==============================================================================
# 2. 기상 기준 판정 및 좌표 변환 유틸리티
# ==============================================================================


def determine_weather_event(
    sum_rn: float, max_ws: float, max_ta: float, min_ta: float
) -> tuple[str, str]:
    """
    관측치(강수량, 풍속, 기온)를 종합 분석하여 내부 기상 명칭 및 표준 이벤트 코드를 판정합니다.

    Returns:
        tuple[str, str]: (날씨 명칭, weather_event 코드)
        - weather_event 규격: HEAVY_RAIN(집중호우), TYPHOON(강풍/태풍), HEAT_WAVE(폭염),
                             COLD_WAVE(한파), RAIN(비), CLEAR(맑음)
    """
    if sum_rn >= 50.0:
        return "집중호우", "HEAVY_RAIN"
    if max_ws >= 14.0 or (max_ws >= 10.0 and sum_rn >= 20.0):
        return "강풍/태풍", "TYPHOON"
    if max_ta >= 33.0:
        return "폭염", "HEAT_WAVE"
    if min_ta <= -12.0:
        return "한파", "COLD_WAVE"
    if sum_rn > 0.0:
        return "비", "RAIN"
    return "맑음", "CLEAR"


def _convert_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """
    WGS84 위경도 좌표(Lambert Conformal Conic 투영법 기준)를 기상청 단기예보 격자 좌표(nx, ny)로 변환합니다.

    Args:
        lat (float): 위도
        lon (float): 경도

    Returns:
        tuple[int, int]: (nx, ny) 기상청 격자 좌표
    """
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0  # 격자 간격(km)
    SLAT1 = 30.0  # 투영 위도 1(degree)
    SLAT2 = 60.0  # 투영 위도 2(degree)
    OLON = 126.0  # 기준점 경도(degree)
    OLAT = 38.0  # 기준점 위도(degree)
    XO = 43  # 기준점 X좌표(GRID)
    YO = 136  # 기준점 Y좌표(GRID)

    DEGRAD = math.pi / 180.0

    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (math.pow(sf, sn) * math.cos(slat1)) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = (re * sf) / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = (re * sf) / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(math.floor(ra * math.sin(theta) + XO + 0.5))
    ny = int(math.floor(ro - ra * math.cos(theta) + YO + 0.5))
    return nx, ny


# ==============================================================================
# 3. 실시간 기상 조회 (신규 현장 점검 등록 시 호출)
# ==============================================================================


def fetch_realtime_weather(coordinates: str) -> dict:
    """
    현장 점검 시점의 위경도 좌표를 바탕으로 기상청 초단기실황 API를 호출하여 실시간 기상을 수집합니다.
    (네트워크 장애 또는 미설정 시 서비스가 중단되지 않도록 기본 맑음 값을 안전하게 반환합니다.)

    Args:
        coordinates (str): '위도, 경도' 형태의 문자열 (예: '37.123456, 127.123456')

    Returns:
        dict: {"weather": str, "rainfall": float, "weather_event": str}
    """
    default_weather = {"weather": "맑음", "rainfall": 0.0, "weather_event": "CLEAR"}

    if not WEATHER_API_KEY or not coordinates or "," not in coordinates:
        return default_weather

    try:
        lat_str, lng_str = coordinates.split(",")
        lat, lng = float(lat_str.strip()), float(lng_str.strip())
        nx, ny = _convert_to_grid(lat, lng)

        now = datetime.now()
        base_date = now.strftime("%Y%m%d")
        base_time = now.strftime("%H00")

        params = {
            "serviceKey": WEATHER_API_KEY,
            "pageNo": 1,
            "numOfRows": 100,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        }

        res = requests.get(ULTRA_SRT_NCST_URL, params=params, timeout=4)
        if res.status_code != 200:
            return default_weather

        body = res.json().get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if not items:
            return default_weather

        rn1 = 0.0  # 1시간 강수량 (단위: mm)
        pty = "0"  # 강수 형태 코드 (0: 없음, 1: 비, 2: 비/눈, 3: 눈, 5: 빗방울, 6: 빗방울눈날림, 7: 눈날림)

        for item in items:
            category = item.get("category")
            val = item.get("obsrValue")
            if category == "RN1":
                try:
                    rn1 = float(val) if float(val) > 0 else 0.0
                except (ValueError, TypeError):
                    rn1 = 0.0
            elif category == "PTY":
                pty = str(val)

        # 실시간 강수량 및 강수 형태 기반 이벤트 분류
        if rn1 >= 30.0:
            return {
                "weather": "집중호우",
                "rainfall": rn1,
                "weather_event": "HEAVY_RAIN",
            }
        if rn1 > 0.0 or pty in ["1", "2", "5"]:
            return {"weather": "비", "rainfall": rn1, "weather_event": "RAIN"}
        if pty in ["3", "7"]:
            return {"weather": "눈", "rainfall": 0.0, "weather_event": "SNOW"}

        return {"weather": "맑음", "rainfall": 0.0, "weather_event": "CLEAR"}

    except Exception as e:
        print(f"⚠️ 실시간 기상 조회 예외 발생 (기본값 처리): {e}")
        return default_weather


# ==============================================================================
# 4. 과거 기상 이력 백필(Backfill) 프로세스
# ==============================================================================


def backfill_inspections_weather(force_update: bool = True):
    """
    DB에 누적된 과거 점검 데이터의 촬영 일시 및 권역을 집계하여,
    기상청 종관기상관측(ASOS) 과거 일자료를 수집하고 inspections 테이블을 일괄 갱신합니다.

    Args:
        force_update (bool): True일 경우 기존에 기상 데이터가 존재해도 최신 관측치로 덮어씁니다.
    """
    if not WEATHER_API_KEY:
        print("❌ WEATHER_API_KEY가 .env 파일에 설정되지 않았습니다.")
        return

    where_clause = "WHERE i.deleted_at IS NULL"
    if not force_update:
        where_clause += (
            " AND (i.weather IS NULL OR i.weather = '' OR i.rainfall IS NULL)"
        )

    # 1. 수집 대상 고유 일자 및 권역 접두사(주소 앞 2글자) 추출
    query = f"""
        SELECT 
            DATE_FORMAT(i.captured_at, '%%Y%%m%%d') AS dt,
            DATE(i.captured_at) AS raw_date,
            SUBSTRING(l.address, 1, 2) AS region_prefix
        FROM inspections i
        LEFT JOIN locations l ON i.location_id = l.id
        {where_clause}
        GROUP BY DATE_FORMAT(i.captured_at, '%%Y%%m%%d'), DATE(i.captured_at), SUBSTRING(l.address, 1, 2)
        ORDER BY raw_date ASC
    """
    rows = fetch_query(query) or []

    if not rows:
        print("업데이트 대상 점검 데이터가 존재하지 않습니다.")
        return

    all_dts = [r["dt"] for r in rows if r.get("dt")]
    min_date = min(all_dts)

    # ASOS 일자료는 일 마감 집계 특성상 당일 데이터 조회가 불가하므로 어제(D-1) 날짜로 보정
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    raw_max_date = max(all_dts)
    max_date = min(raw_max_date, yesterday_str)

    if min_date > max_date:
        print(
            f"⚠️ 점검 데이터가 모두 오늘({raw_max_date}) 생성되어 과거 일자료 조회 대상이 없습니다."
        )
        return

    # 점검 지역에 매핑되는 고유 ASOS 관측소 지점 번호 선별
    target_stn_ids = set()
    for r in rows:
        prefix = r.get("region_prefix") or ""
        stn = REGION_STATION_MAP.get(prefix, 108)
        target_stn_ids.add(stn)

    print(
        f"📡 기상청 ASOS 수집 시작: {min_date} ~ {max_date} | 대상 지점 수: {len(target_stn_ids)}개 ({target_stn_ids})"
    )

    # 날짜 및 지역 조건을 만족하는 점검 레코드 기상 정보 일괄 갱신 쿼리
    update_sql = """
        UPDATE inspections i
        JOIN locations l ON i.location_id = l.id
        SET i.weather = %s, i.rainfall = %s, i.weather_event = %s
        WHERE DATE(i.captured_at) = %s 
          AND (l.address LIKE CONCAT(%s, '%%') OR %s = '기타')
    """

    total_updated = 0

    # 2. 지점별 API 호출 및 DB 반영
    for stn_id in target_stn_ids:
        region_name = next(
            (k for k, v in REGION_STATION_MAP.items() if v == stn_id), "기타"
        )

        params = {
            "serviceKey": WEATHER_API_KEY,
            "numOfRows": 999,
            "pageNo": 1,
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "DAY",
            "startDt": min_date,
            "endDt": max_date,
            "stnIds": stn_id,
        }

        try:
            res = requests.get(ASOS_URL, params=params, timeout=15)

            # API 호출 상태 및 인증 에러 점검
            if (
                res.status_code != 200
                or "SERVICE_KEY" in res.text
                or "<returnAuthMsg>" in res.text
            ):
                print(f"❌ 지점 {stn_id} 기상청 API 응답 이상: {res.text[:200]}")
                continue

            res_json = res.json()
            body = res_json.get("response", {}).get("body", {})
            header = res_json.get("response", {}).get("header", {})

            # 기상청 정상 응답 코드("00") 확인
            if header.get("resultCode") != "00":
                print(f"⚠️ 지점 {stn_id} 기상청 응답 메시지: {header.get('resultMsg')}")
                continue

            items = body.get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]

            if not items:
                print(f"⚠️ 지점 {stn_id} ({region_name}) 데이터가 0건 반환되었습니다.")
                continue

            # 수집된 관측 데이터를 순회하며 기상 이벤트 판별 및 UPDATE 실행
            for it in items:
                tm_str = it.get("tm")  # 관측 일자 ('YYYY-MM-DD')
                sum_rn = (
                    float(it["sumRn"])
                    if it.get("sumRn") and it["sumRn"].strip()
                    else 0.0
                )
                max_ws = (
                    float(it["maxWs"])
                    if it.get("maxWs") and it["maxWs"].strip()
                    else 0.0
                )
                max_ta = (
                    float(it["maxTa"])
                    if it.get("maxTa") and it["maxTa"].strip()
                    else 0.0
                )
                min_ta = (
                    float(it["minTa"])
                    if it.get("minTa") and it["minTa"].strip()
                    else 0.0
                )

                weather_desc, event = determine_weather_event(
                    sum_rn, max_ws, max_ta, min_ta
                )

                execute_query(
                    update_sql,
                    (weather_desc, sum_rn, event, tm_str, region_name, region_name),
                )
                total_updated += 1

            print(
                f"  ✓ 지점 {stn_id}({region_name}) 기상 데이터 반영 완료 ({len(items)}일치)"
            )

        except Exception as e:
            print(f"❌ 지점 {stn_id} 데이터 처리 중 예외 발생: {e}")

    print(
        f"🎉 완료: 실제 기상청 날씨/강수량 데이터가 DB에 반영되었습니다. (총 처리 건수: {total_updated})"
    )


# ==============================================================================
# 5. 스크립트 직접 실행 진입점
# ==============================================================================

if __name__ == "__main__":
    backfill_inspections_weather(force_update=True)
