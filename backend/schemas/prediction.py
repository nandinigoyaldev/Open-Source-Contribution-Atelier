from pydantic import BaseModel, Field, validator
from typing import Optional, List


class PredictionRequestSchema(BaseModel):
    """Schema for spam prediction request"""

    text: str = Field(..., min_length=1, max_length=5000)
    type: str = Field(..., description="Type of input: message, email, url, sms")

    @validator("type")
    def validate_type(cls, v):
        allowed = ["message", "email", "url", "sms"]
        if v.lower() not in allowed:
            raise ValueError(f'Type must be one of: {", ".join(allowed)}')
        return v.lower()


class PredictionResponseSchema(BaseModel):
    """Schema for spam prediction response"""

    prediction: str = Field(
        ..., description="Prediction result: spam, ham, malicious, smishing"
    )
    confidence: float = Field(..., ge=0, le=1)
    explanation: Optional[dict] = None

    class Config:
        from_attributes = True
