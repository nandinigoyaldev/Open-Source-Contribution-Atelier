from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Annotated

# ============================================
# BASE SCHEMA WITH COMMON VALIDATIONS
# ============================================

class BaseLessonSchema(BaseModel):
    """Base schema with common validations for all lesson schemas."""
    
    title: Annotated[
        str,
        Field(
            min_length=3,
            max_length=200,
            description="Lesson title (3-200 characters)",
            examples=["Introduction to Git", "Understanding Open Source"],
        )
    ]
    content: Annotated[
        str,
        Field(
            min_length=10,
            description="Lesson content in Markdown format (minimum 10 characters)",
            examples=["# Lesson 1\n\nWelcome to the world of open source..."],
        )
    ]
    module_id: Annotated[
        int,
        Field(
            gt=0,
            description="ID of the module this lesson belongs to",
            examples=[1, 2, 3],
        )
    ]
    order: Annotated[
        int,
        Field(
            ge=0,
            description="Display order within the module (0-based)",
            examples=[0, 1, 2],
        )
    ]
    is_published: bool = Field(
        default=False,
        description="Whether this lesson is published and visible to users",
    )

    # ===== VALIDATORS =====

    @field_validator("title", mode="after")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Strip whitespace and ensure title is not empty after stripping."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty or only whitespace")
        if len(stripped) < 3:
            raise ValueError("Title must be at least 3 characters after trimming")
        return stripped

    @field_validator("content", mode="after")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Strip whitespace and ensure content is not empty after stripping."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Content cannot be empty or only whitespace")
        if len(stripped) < 10:
            raise ValueError("Content must be at least 10 characters after trimming")
        return stripped

    @field_validator("order", mode="after")
    @classmethod
    def validate_order(cls, v: int) -> int:
        """Ensure order is non-negative."""
        if v < 0:
            raise ValueError("Order must be a non-negative integer")
        return v

    @model_validator(mode="after")
    def validate_unique_order_per_module(self) -> "BaseLessonSchema":
        """
        If you have access to the database, you can check that order is unique
        within the module. This is a placeholder; implement with DB query if needed.
        """
        # In a real scenario, you'd query the DB for existing lessons in this module
        # and check if the order conflicts. This would require a service layer.
        # Since this is a schema, we leave it for the service layer.
        return self


# ============================================
# CREATE SCHEMA
# ============================================

class LessonCreateSchema(BaseLessonSchema):
    """Schema for creating a new lesson."""
    
    # Inherits all fields from BaseLessonSchema
    # Additional fields specific to creation can be added here
    pass


# ============================================
# UPDATE SCHEMA
# ============================================

class LessonUpdateSchema(BaseModel):
    """Schema for updating an existing lesson. All fields are optional."""
    
    title: Annotated[
        Optional[str],
        Field(
            min_length=3,
            max_length=200,
            description="Lesson title (3-200 characters)",
            examples=["Updated: Introduction to Git"],
        )
    ] = None
    content: Annotated[
        Optional[str],
        Field(
            min_length=10,
            description="Lesson content in Markdown format",
            examples=["# Updated Content\n\nNew learning materials..."],
        )
    ] = None
    module_id: Annotated[
        Optional[int],
        Field(
            gt=0,
            description="ID of the module this lesson belongs to",
        )
    ] = None
    order: Annotated[
        Optional[int],
        Field(
            ge=0,
            description="Display order within the module",
        )
    ] = None
    is_published: Optional[bool] = Field(
        default=None,
        description="Whether this lesson is published",
    )

    # ===== VALIDATORS =====

    @field_validator("title", mode="after")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Title cannot be empty or only whitespace")
            if len(stripped) < 3:
                raise ValueError("Title must be at least 3 characters after trimming")
            return stripped
        return v

    @field_validator("content", mode="after")
    @classmethod
    def validate_content(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Content cannot be empty or only whitespace")
            if len(stripped) < 10:
                raise ValueError("Content must be at least 10 characters after trimming")
            return stripped
        return v


# ============================================
# RESPONSE SCHEMA
# ============================================

class LessonResponseSchema(BaseModel):
    """Schema for lesson response (includes computed fields)."""
    
    id: int = Field(..., description="Unique identifier for the lesson")
    title: str
    content: str
    module_id: int
    order: int
    is_published: bool
    created_at: datetime
    updated_at: datetime

    # ===== COMPUTED FIELDS =====

    @property
    def word_count(self) -> int:
        """Number of words in the content."""
        return len(self.content.split())

    @property
    def reading_time_minutes(self) -> float:
        """Estimated reading time in minutes (based on 200 wpm)."""
        return round(self.word_count / 200, 1)

    @property
    def content_preview(self) -> str:
        """First 200 characters of content for preview."""
        return self.content[:200] + ("..." if len(self.content) > 200 else "")

    # ===== PYDANTIC V2 CONFIG =====

    model_config = {
        "from_attributes": True,  # equivalent to orm_mode=True in v1
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "title": "Introduction to Git",
                    "content": "# Git Basics\n\nLearn version control...",
                    "module_id": 1,
                    "order": 0,
                    "is_published": True,
                    "created_at": "2024-01-01T10:00:00",
                    "updated_at": "2024-01-02T12:00:00",
                }
            ]
        },
    }

    # For Pydantic v2, you can also use:
    # from pydantic import ConfigDict
    # model_config = ConfigDict(from_attributes=True)


# ============================================
# LIST RESPONSE (PAGINATION)
# ============================================

class LessonListResponseSchema(BaseModel):
    """Schema for paginated list of lessons."""
    
    items: List[LessonResponseSchema]
    total: int
    page: int
    per_page: int
    total_pages: int

    model_config = {"from_attributes": True}


# ============================================
# BULK CREATE SCHEMA (OPTIONAL)
# ============================================

class LessonBulkCreateSchema(BaseModel):
    """Schema for creating multiple lessons at once."""
    
    lessons: List[LessonCreateSchema] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of lessons to create (1-50 items)",
    )

    @model_validator(mode="after")
    def validate_unique_orders(self) -> "LessonBulkCreateSchema":
        """Ensure that within the bulk, no two lessons have the same order in the same module."""
        # Group by module_id and check order duplicates
        from collections import defaultdict
        module_orders = defaultdict(set)
        for lesson in self.lessons:
            key = (lesson.module_id, lesson.order)
            if key in module_orders:
                raise ValueError(
                    f"Duplicate order {lesson.order} in module {lesson.module_id} "
                    "within the bulk create request."
                )
            module_orders.add(key)
        return self