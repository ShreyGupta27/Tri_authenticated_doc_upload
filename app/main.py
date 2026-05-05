"""
Main FastAPI application for document upload service with multi-auth and database integration.
"""
from fastapi import FastAPI, UploadFile, File, Query, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.config import Settings
from app.models import AuthMethod, UploadResponse
from app.database import init_database, get_db_session
from app.auth.database_auth_service import DatabaseAuthService
from app.auth.authenticators import JWTAuthenticator, SecretKeyAuthenticator, CertificateAuthenticator, AuthenticationHandler
from app.validators.document_validator import DocumentValidator
from app.storage.storage_service import StorageService
from app.exceptions import (
    DocumentUploadException,
    AuthenticationException,
    ValidationException,
    StorageException,
    register_exception_handlers
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
settings = Settings()

# Initialize database
db_manager = init_database(settings.database_url)

# Initialize FastAPI app
app = FastAPI(
    title="Document Upload Service",
    description="Multi-authentication document upload service with database-backed auth and Google Cloud Storage",
    version="2.0.0"
)

# Security schemes for Swagger UI
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# Initialize services
database_auth_service = DatabaseAuthService(settings.jwt_secret_key, settings.jwt_algorithm)
document_validator = DocumentValidator()
storage_service = StorageService(settings.gcs_bucket_name)

# Register exception handlers
register_exception_handlers(app)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Document Upload Service v2.0.0")
    
    # Test database connection
    connection_ok = await db_manager.test_connection()
    if not connection_ok:
        logger.error("Failed to connect to database!")
    else:
        logger.info("Database connection established")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Document Upload Service")
    await db_manager.close()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Test database connection
    db_healthy = await db_manager.test_connection()
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "service": "document-upload",
        "version": "2.0.0",
        "database": "connected" if db_healthy else "disconnected"
    }


@app.get("/debug-headers")
async def debug_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_client_cert: Optional[str] = Header(None, alias="X-Client-Cert")
):
    """Debug endpoint to see what headers are being received."""
    return {
        "authorization": authorization,
        "x_api_key": x_api_key,
        "x_client_cert": x_client_cert,
        "authorization_present": authorization is not None,
        "authorization_length": len(authorization) if authorization else 0
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    auth_method: Optional[AuthMethod] = Query(None, description="Authentication method to use"),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_scheme),
    x_client_cert: Optional[str] = Header(None, alias="X-Client-Cert", description="Client certificate PEM"),
    db_session: AsyncSession = Depends(get_db_session)
) -> UploadResponse:
    """
    Upload a document with database-backed authentication.
    
    Supports three authentication methods:
    1. JWT: Provide Bearer token using the "Authorize" button - validated against database
    2. Certificate: Provide client certificate PEM in X-Client-Cert header
    3. Secret Key: Provide API key using the "Authorize" button - validated against database
    
    Args:
        file: The document file to upload
        auth_method: Optional explicit authentication method
        bearer_token: JWT Bearer token from security scheme
        api_key: API key from security scheme
        x_client_cert: Client certificate PEM for certificate authentication
        db_session: Database session
        
    Returns:
        UploadResponse with upload details
        
    Raises:
        HTTPException: For authentication, validation, or storage errors
    """
    logger.info(f"Upload request received for file: {file.filename}")
    
    # Step 1: Validate the document
    logger.debug("Validating document format")
    document_validator.validate(file)
    
    # Step 2: Authenticate the request using database
    logger.debug(f"Authenticating request with method: {auth_method}")
    
    auth_result = await authenticate_request(
        auth_method=auth_method,
        bearer_token=bearer_token,
        api_key=api_key,
        x_client_cert=x_client_cert,
        db_session=db_session
    )
    
    logger.info(f"Authentication successful for user: {auth_result.user_id}")
    
    # Step 3: Upload to storage
    logger.debug("Uploading file to storage")
    object_path = await storage_service.upload(file, auth_result.user_id)
    
    logger.info(f"Upload successful: {object_path}")
    
    # Step 4: Return success response
    return UploadResponse(
        status="success",
        object_path=object_path,
        filename=file.filename or "unknown"
    )


async def authenticate_request(
    auth_method: Optional[AuthMethod],
    bearer_token: Optional[HTTPAuthorizationCredentials],
    api_key: Optional[str],
    x_client_cert: Optional[str],
    db_session: AsyncSession
):
    """
    Authenticate request using database-backed authentication.
    
    Args:
        auth_method: Explicit authentication method
        bearer_token: JWT Bearer token
        api_key: API key
        x_client_cert: Client certificate
        db_session: Database session
        
    Returns:
        AuthResult from successful authentication
        
    Raises:
        AuthenticationException: For authentication failures
    """
    # Extract credentials
    jwt_token = bearer_token.credentials if bearer_token else None
    
    # If method is explicitly specified, use only that method
    if auth_method:
        if auth_method == AuthMethod.JWT:
            if not jwt_token:
                raise AuthenticationException("AUTH_MISSING", "JWT token is required")
            return await database_auth_service.validate_jwt_token(jwt_token, db_session)
        
        elif auth_method == AuthMethod.SECRET_KEY:
            if not api_key:
                raise AuthenticationException("AUTH_MISSING", "API key is required")
            return await database_auth_service.validate_api_key(api_key, db_session)
        
        elif auth_method == AuthMethod.CERTIFICATE:
            if not x_client_cert:
                raise AuthenticationException("AUTH_MISSING", "Client certificate is required")
            # Certificate authentication not implemented with database yet
            raise AuthenticationException("AUTH_METHOD_NOT_SUPPORTED", "Certificate authentication not yet supported with database")
    
    # Auto-detect authentication method
    provided_methods = []
    if jwt_token:
        provided_methods.append("jwt")
    if api_key:
        provided_methods.append("api_key")
    if x_client_cert:
        provided_methods.append("certificate")
    
    if len(provided_methods) == 0:
        raise AuthenticationException("AUTH_MISSING", "No authentication credentials provided")
    
    if len(provided_methods) > 1:
        raise AuthenticationException(
            "VALIDATION_AMBIGUOUS_AUTH",
            f"Multiple authentication credentials provided: {', '.join(provided_methods)}. Specify auth_method parameter to choose one."
        )
    
    # Authenticate with the single provided method
    if jwt_token:
        return await database_auth_service.validate_jwt_token(jwt_token, db_session)
    elif api_key:
        return await database_auth_service.validate_api_key(api_key, db_session)
    else:
        raise AuthenticationException("AUTH_METHOD_NOT_SUPPORTED", "Certificate authentication not yet supported with database")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)