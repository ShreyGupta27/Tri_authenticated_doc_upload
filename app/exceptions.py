"""
Custom exceptions and error handling for the document upload service.
"""
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DocumentUploadException(Exception):
    """Base exception for document upload service."""
    
    def __init__(self, error_code: str, message: str, status_code: int = 500, details: Dict[str, Any] = None):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationException(DocumentUploadException):
    """Exception for authentication failures."""
    
    def __init__(self, error_code: str, message: str, details: Dict[str, Any] = None):
        super().__init__(error_code, message, 401, details)


class ValidationException(DocumentUploadException):
    """Exception for validation failures."""
    
    def __init__(self, error_code: str, message: str, details: Dict[str, Any] = None):
        super().__init__(error_code, message, 400, details)


class StorageException(DocumentUploadException):
    """Exception for storage failures."""
    
    def __init__(self, error_code: str, message: str, details: Dict[str, Any] = None):
        super().__init__(error_code, message, 500, details)


def create_error_response(error_code: str, message: str, status_code: int, details: Dict[str, Any] = None) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        error_code: Error code identifier
        message: Human-readable error message
        status_code: HTTP status code
        details: Optional additional error details
        
    Returns:
        JSONResponse with standardized error format
    """
    error_content = {
        "error_code": error_code,
        "message": message
    }
    
    if details:
        # Filter out sensitive information from details
        filtered_details = {k: v for k, v in details.items() 
                          if not any(sensitive in k.lower() 
                                   for sensitive in ['password', 'secret', 'key', 'token', 'auth'])}
        if filtered_details:
            error_content["details"] = filtered_details
    
    return JSONResponse(
        status_code=status_code,
        content=error_content
    )


async def document_upload_exception_handler(request: Request, exc: DocumentUploadException) -> JSONResponse:
    """
    Handle custom DocumentUploadException instances.
    
    Args:
        request: FastAPI request object
        exc: The exception instance
        
    Returns:
        JSONResponse with error details
    """
    logger.warning(f"Document upload exception: {exc.error_code} - {exc.message}")
    
    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTPException instances.
    
    Args:
        request: FastAPI request object
        exc: The HTTPException instance
        
    Returns:
        JSONResponse with error details
    """
    # Check if the detail is already in our expected format
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Convert generic HTTPException to our format
    error_code = "HTTP_ERROR"
    if exc.status_code == 401:
        error_code = "AUTH_MISSING"
    elif exc.status_code == 400:
        error_code = "VALIDATION_ERROR"
    elif exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 500:
        error_code = "INTERNAL_ERROR"
    
    return create_error_response(
        error_code=error_code,
        message=str(exc.detail),
        status_code=exc.status_code
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle FastAPI request validation errors.
    
    Args:
        request: FastAPI request object
        exc: The RequestValidationError instance
        
    Returns:
        JSONResponse with validation error details
    """
    logger.warning(f"Request validation error: {exc.errors()}")
    
    # Extract validation errors
    validation_errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        validation_errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=400,
        details={"validation_errors": validation_errors}
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.
    
    Args:
        request: FastAPI request object
        exc: The exception instance
        
    Returns:
        JSONResponse with generic error message
    """
    logger.error(f"Unexpected error: {type(exc).__name__}: {str(exc)}", exc_info=True)
    
    return create_error_response(
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        status_code=500
    )


def auth_error(error_code: str, message: str) -> HTTPException:
    """
    Create a standardized authentication error response.
    
    Args:
        error_code: Error code identifier
        message: Human-readable error message
        
    Returns:
        HTTPException with 401 status and standardized format
    """
    return HTTPException(
        status_code=401,
        detail={
            "error_code": error_code,
            "message": message
        }
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(DocumentUploadException, document_upload_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)