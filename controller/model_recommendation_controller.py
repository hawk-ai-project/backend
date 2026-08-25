from fastapi import APIRouter, Depends

from controller.auth_controller import current_auth
from domain.model_recommendation import ModelRecommendationRequest, ModelRecommendationResponse
from service import model_recommendation_service


router = APIRouter(prefix="/api/ai/model-recommendations", tags=["AI Model Recommendation"])


@router.post("", response_model=ModelRecommendationResponse)
def recommend_model(payload: ModelRecommendationRequest, auth=Depends(current_auth)):
    return model_recommendation_service.recommend(payload, auth[0])


@router.get("/cached/global", response_model=ModelRecommendationResponse)
def cached_global_recommendation(auth=Depends(current_auth)):
    return model_recommendation_service.get_cached_global(auth[0])


@router.get("/cached/reinspections/{inspection_id}", response_model=ModelRecommendationResponse)
def cached_reinspection_recommendation(inspection_id: int, auth=Depends(current_auth)):
    return model_recommendation_service.get_cached_reinspection(inspection_id, auth[0])
