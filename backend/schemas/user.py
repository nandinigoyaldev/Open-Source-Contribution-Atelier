from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


class UserCreateSchema(BaseModel):
    """Schema for user registration"""

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password")
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)

    @validator("password")
    def validate_password(cls, v):
        """Validate password strength"""
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v


class UserLoginSchema(BaseModel):
    """Schema for user login"""

    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class UserResponseSchema(BaseModel):
    """Schema for user response"""

    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    date_joined: datetime
    is_active: bool

    class Config:
        from_attributes = True


class UserProfileSchema(BaseModel):
    """Schema for user profile details"""

    id: int
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class LoginResponseSchema(BaseModel):
    """Schema for successful login response"""

    key: str = Field(..., description="Authentication Token")
    user: UserResponseSchema
