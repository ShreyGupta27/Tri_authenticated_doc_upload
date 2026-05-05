from enum import Enum
from pydantic import BaseModel
from typing import Optional


class AuthMethod(str, Enum):
    JWT = "jwt"
    CERTIFICATE = "certificate"
    SECRET_KEY = "secret_key"


class AuthResult:
    """Result of successful authentication."""
    
    def __init__(self, user_id: str, method: AuthMethod, metadata: Optional[dict] = None):
        self.user_id = user_id
        self.method = method
        self.metadata = metadata or {}


class UploadResponse(BaseModel):
    """Response model for successful upload."""
    status: str
    object_path: str
    filename: str


class ErrorResponse(BaseModel):
    """Response model for errors."""
    error_code: str
    message: str
    details: Optional[dict] = None
