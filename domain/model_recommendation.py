from enum import Enum

from pydantic import BaseModel, Field, model_validator


class RecommendationContextType(str, Enum):
    GLOBAL = "GLOBAL"
    INSPECTION = "INSPECTION"
    REINSPECTION = "REINSPECTION"


class ModelRecommendationRequest(BaseModel):
    contextType: RecommendationContextType
    inspectionId: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_inspection_id(self):
        if self.contextType == RecommendationContextType.GLOBAL and self.inspectionId is not None:
            raise ValueError("GLOBAL context must not include inspectionId")
        if self.contextType != RecommendationContextType.GLOBAL and self.inspectionId is None:
            raise ValueError("inspectionId is required for inspection contexts")
        return self


class RankedModelRecommendation(BaseModel):
    rank: int = Field(ge=1, le=3)
    modelId: str
    modelName: str
    label: str
    summary: str
    strengths: list[str]
    bestFor: list[str]
    tradeoffs: list[str]
    reasons: list[str] = Field(default_factory=list)


class ModelRecommendationResponse(BaseModel):
    contextType: RecommendationContextType
    recommendedModelId: str
    recommendedModelName: str
    currentModelId: str | None = None
    confidence: float = Field(ge=0, le=1)
    summary: str
    reasons: list[str]
    warnings: list[str]
    candidateCount: int = Field(ge=1)
    recommendations: list[RankedModelRecommendation] = Field(min_length=1, max_length=3)
