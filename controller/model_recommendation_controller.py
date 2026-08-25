from fastapi import APIRouter, Depends

from controller.auth_controller import current_auth
from domain.model_recommendation import ModelRecommendationRequest, ModelRecommendationResponse
from service import model_recommendation_service


router = APIRouter(prefix="/api/ai/model-recommendations", tags=["AI Model Recommendation"])


@router.post("", response_model=ModelRecommendationResponse)
def recommend_model(payload: ModelRecommendationRequest, auth=Depends(current_auth)):
    return model_recommendation_service.recommend(payload, auth[0])
