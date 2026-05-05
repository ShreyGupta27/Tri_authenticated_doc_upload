"""
Database-backed authentication service for JWT tokens and API keys.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
import logging
import jwt
from datetime import datetime

from app.database import User
from app.models import AuthResult, AuthMethod
from app.exceptions import AuthenticationException

logger = logging.getLogger(__name__)


class DatabaseAuthService:
    """Service for database-backed authentication."""
    
    def __init__(self, jwt_secret_key: str, jwt_algorithm: str = "HS256"):
        """
        Initialize database auth service.
        
        Args:
            jwt_secret_key: Secret key for JWT validation
            jwt_algorithm: JWT algorithm (default: HS256)
        """
        self.jwt_secret_key = jwt_secret_key
        self.jwt_algorithm = jwt_algorithm
    
    async def validate_jwt_token(self, token: str, db_session: AsyncSession) -> AuthResult:
        """
        Validate JWT token against database.
        
        Args:
            token: JWT token to validate
            db_session: Database session
            
        Returns:
            AuthResult with user information
            
        Raises:
            AuthenticationException: If token is invalid or not found in database
        """
        try:
            # First, decode and validate the JWT token structure
            payload = jwt.decode(
                token,
                self.jwt_secret_key,
                algorithms=[self.jwt_algorithm]
            )
            
            user_id = payload.get("user_id")
            if not user_id:
                raise AuthenticationException(
                    "AUTH_TOKEN_INVALID",
                    "JWT token missing user_id claim"
                )
            
            # Check if token exists in database
            stmt = select(User).where(User.jwtToken == token)
            result = await db_session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise AuthenticationException(
                    "AUTH_TOKEN_INVALID",
                    "JWT token not found in database"
                )
            
            logger.info(f"JWT token validated for user ID: {user_id}")
            
            return AuthResult(
                user_id=user_id,
                method=AuthMethod.JWT,
                metadata={
                    "database_user_id": user.id,
                    "token_exp": payload.get("exp")
                }
            )
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationException(
                "AUTH_TOKEN_EXPIRED",
                "JWT token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise AuthenticationException(
                "AUTH_TOKEN_INVALID",
                f"JWT token is malformed or has invalid signature: {str(e)}"
            )
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            raise AuthenticationException(
                "AUTH_TOKEN_INVALID",
                "Failed to validate JWT token"
            )
    
    async def validate_api_key(self, api_key: str, db_session: AsyncSession) -> AuthResult:
        """
        Validate API key against database.
        
        Args:
            api_key: API key to validate
            db_session: Database session
            
        Returns:
            AuthResult with user information
            
        Raises:
            AuthenticationException: If API key is invalid or not found
        """
        try:
            # Check if API key exists in database
            stmt = select(User).where(User.webhookApiKey == api_key)
            result = await db_session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise AuthenticationException(
                    "AUTH_KEY_INVALID",
                    "API key not found in database"
                )
            
            logger.info(f"API key validated for database user ID: {user.id}")
            
            return AuthResult(
                user_id=f"user_{user.id}",  # Create user_id from database ID
                method=AuthMethod.SECRET_KEY,
                metadata={
                    "database_user_id": user.id,
                    "api_key": api_key[:8] + "..." if len(api_key) > 8 else api_key  # Truncated for security
                }
            )
            
        except AuthenticationException:
            raise
        except Exception as e:
            logger.error(f"API key validation error: {e}")
            raise AuthenticationException(
                "AUTH_KEY_INVALID",
                "Failed to validate API key"
            )
    
    async def validate_webhook_secret(self, secret_key: str, db_session: AsyncSession) -> AuthResult:
        """
        Validate webhook secret key against database.
        
        Args:
            secret_key: Webhook secret key to validate
            db_session: Database session
            
        Returns:
            AuthResult with user information
            
        Raises:
            AuthenticationException: If secret key is invalid or not found
        """
        try:
            # Check if webhook secret exists in database
            stmt = select(User).where(User.webhookSecretKey == secret_key)
            result = await db_session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise AuthenticationException(
                    "AUTH_KEY_INVALID",
                    "Webhook secret key not found in database"
                )
            
            logger.info(f"Webhook secret validated for database user ID: {user.id}")
            
            return AuthResult(
                user_id=f"user_{user.id}",
                method=AuthMethod.SECRET_KEY,
                metadata={
                    "database_user_id": user.id,
                    "auth_type": "webhook_secret"
                }
            )
            
        except AuthenticationException:
            raise
        except Exception as e:
            logger.error(f"Webhook secret validation error: {e}")
            raise AuthenticationException(
                "AUTH_KEY_INVALID",
                "Failed to validate webhook secret key"
            )
    
    async def get_user_by_id(self, user_id: int, db_session: AsyncSession) -> Optional[User]:
        """
        Get user by database ID.
        
        Args:
            user_id: Database user ID
            db_session: Database session
            
        Returns:
            User object or None if not found
        """
        try:
            stmt = select(User).where(User.id == user_id)
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            return None