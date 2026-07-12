from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class LessonCreateSchema(BaseModel):
    """Schema for creating a lesson"""

    title: str = Field(..., min_length=3, max_length=200)
    content: str = Field(..., min_length=10)
    module_id: int = Field(..., gt=0)
    order: int = Field(..., ge=0)
    is_published: bool = False

    @validator("content")
    def validate_content(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Content must be at least 10 characters")
        return v


class LessonUpdateSchema(BaseModel):
    """Schema for updating a lesson"""

    title: Optional[str] = Field(None, min_length=3, max_length=200)
    content: Optional[str] = Field(None, min_length=10)
    order: Optional[int] = Field(None, ge=0)
    is_published: Optional[bool] = None


class LessonResponseSchema(BaseModel):
    """Schema for lesson response"""

    id: int
    title: str
    content: str
    module_id: int
    order: int
    is_published: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
