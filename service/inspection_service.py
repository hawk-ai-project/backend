# backend/service/inspection_service.py

from domain.inspection import InspectionRequest, InspectionResponse

def analyze_image(payload: InspectionRequest) -> InspectionResponse:
# 터미널에 수신 확인 로그
    print(f"프론트엔드에서 사진 수신 완료, 데이터 길이 : {len(payload.image)}")

    # 추후 AI모델로 사진 분석하는 코드 입력

    # 분석 후 백엔드에서 프론트로 보낼 결과
    return InspectionResponse(
        message="사진을 전달받았습니다.",
        result="OK"
    )