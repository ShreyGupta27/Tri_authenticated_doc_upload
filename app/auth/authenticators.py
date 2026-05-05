"""
Consolidated authentication module with all authenticator classes and routing logic.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict
import jwt
import base64
import logging
from fastapi import HTTPException, Request
from cryptography import x509
from cryptography.x509.oid import NameOID

from app.models import AuthResult, AuthMethod
from app.exceptions import auth_error

logger = logging.getLogger(__name__)


class JWTAuthenticator:
    """Validates JWT tokens using PyJWT library."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    async def authenticate(self, token: str) -> AuthResult:
        """
        Validate JWT token and extract user claims.
        
        Args:
            token: JWT token string (without 'Bearer ' prefix)
            
        Returns:
            AuthResult with user_id from token claims
            
        Raises:
            HTTPException: 401 error for invalid/expired/malformed tokens
        """
        try:
            # Decode and validate the token
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            
            # Extract user_id from claims
            user_id = payload.get("user_id") or payload.get("sub")
            if not user_id:
                raise auth_error("AUTH_TOKEN_INVALID", "Token missing user_id or sub claim")
            
            return AuthResult(
                user_id=str(user_id),
                method=AuthMethod.JWT,
                metadata={"claims": payload}
            )
            
        except jwt.ExpiredSignatureError:
            raise auth_error("AUTH_TOKEN_EXPIRED", "JWT token has expired")
        except jwt.InvalidTokenError:
            raise auth_error("AUTH_TOKEN_INVALID", "JWT token is malformed or has invalid signature")
        except HTTPException:
            raise
        except Exception as e:
            raise auth_error("AUTH_TOKEN_INVALID", f"Token validation failed: {str(e)}")
    
    def _extract_token(self, authorization_header: str) -> str:
        """
        Extract token from 'Bearer <token>' format.
        
        Args:
            authorization_header: Authorization header value
            
        Returns:
            JWT token string without 'Bearer ' prefix
            
        Raises:
            HTTPException: 401 error if header format is invalid
        """
        if not authorization_header:
            raise auth_error("AUTH_MISSING", "Authorization header is missing")
        
        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise auth_error("AUTH_TOKEN_INVALID", "Authorization header must be 'Bearer <token>'")
        
        return parts[1]
    
    async def authenticate_from_header(self, authorization_header: Optional[str]) -> AuthResult:
        """
        Authenticate using Authorization header.
        
        Args:
            authorization_header: Authorization header value
            
        Returns:
            AuthResult with user_id from token claims
            
        Raises:
            HTTPException: 401 error for missing/invalid headers or tokens
        """
        token = self._extract_token(authorization_header)
        return await self.authenticate(token)


class SecretKeyAuthenticator:
    """Validates API keys against a configured set of valid keys."""
    
    def __init__(self, valid_keys: Dict[str, str]):
        """
        Initialize secret key authenticator.
        
        Args:
            valid_keys: mapping of api_key -> app_name
        """
        self.valid_keys = valid_keys or {}
    
    async def authenticate(self, api_key: str) -> AuthResult:
        """
        Validate API key against configured keys.
        
        Args:
            api_key: API key to validate
            
        Returns:
            AuthResult with user_id as app_name from valid_keys mapping
            
        Raises:
            HTTPException: 401 error for invalid keys
        """
        if not api_key:
            raise auth_error("AUTH_KEY_INVALID", "API key is missing")
        
        if api_key not in self.valid_keys:
            raise auth_error("AUTH_KEY_INVALID", "API key is not valid")
        
        app_name = self.valid_keys[api_key]
        
        return AuthResult(
            user_id=app_name,
            method=AuthMethod.SECRET_KEY,
            metadata={
                "api_key": api_key[:8] + "..." if len(api_key) > 8 else api_key,
                "app_name": app_name
            }
        )
    
    async def authenticate_from_header(self, api_key_header: Optional[str]) -> AuthResult:
        """
        Authenticate using X-API-Key header.
        
        Args:
            api_key_header: X-API-Key header value
            
        Returns:
            AuthResult with user_id as app_name
            
        Raises:
            HTTPException: 401 error for missing/invalid headers or keys
        """
        if not api_key_header:
            raise auth_error("AUTH_MISSING", "X-API-Key header is missing")
        
        return await self.authenticate(api_key_header.strip())
    
    def add_key(self, api_key: str, app_name: str) -> None:
        """
        Add a new valid API key.
        
        Args:
            api_key: The API key to add
            app_name: The application name associated with the key
        """
        self.valid_keys[api_key] = app_name
    
    def remove_key(self, api_key: str) -> bool:
        """
        Remove an API key.
        
        Args:
            api_key: The API key to remove
            
        Returns:
            True if key was removed, False if key didn't exist
        """
        if api_key in self.valid_keys:
            del self.valid_keys[api_key]
            return True
        return False
    
    def list_apps(self) -> Dict[str, str]:
        """
        Get a copy of the current valid keys mapping.
        
        Returns:
            Dictionary mapping api_key -> app_name
        """
        return self.valid_keys.copy()


class CertificateAuthenticator:
    """Validates client certificates using cryptography library."""
    
    def __init__(self, trusted_ca_certs: List[str]):
        """
        Initialize certificate authenticator.
        
        Args:
            trusted_ca_certs: List of PEM-encoded trusted CA certificates
        """
        self.trusted_ca_certs = []
        for ca_cert_pem in trusted_ca_certs:
            try:
                ca_cert = x509.load_pem_x509_certificate(ca_cert_pem.encode())
                self.trusted_ca_certs.append(ca_cert)
            except Exception:
                # Log warning but continue - allows for flexible CA cert loading
                pass
    
    async def authenticate(self, cert_pem: str) -> AuthResult:
        """
        Validate client certificate and extract subject.
        
        Args:
            cert_pem: PEM-encoded client certificate
            
        Returns:
            AuthResult with user_id from certificate subject CN
            
        Raises:
            HTTPException: 401 error for invalid/expired/untrusted certificates
        """
        try:
            # Parse the certificate
            cert = x509.load_pem_x509_certificate(cert_pem.encode())
            
            # Validate certificate
            if not self._validate_certificate(cert):
                raise auth_error("AUTH_CERT_UNTRUSTED", "Client certificate is not signed by a trusted CA")
            
            # Check if certificate is expired
            now = datetime.now(timezone.utc)
            if cert.not_valid_after_utc < now:
                raise auth_error("AUTH_CERT_EXPIRED", "Client certificate has expired")
            
            if cert.not_valid_before_utc > now:
                raise auth_error("AUTH_CERT_INVALID", "Client certificate is not yet valid")
            
            # Extract subject CN for user identification
            subject_cn = None
            try:
                subject_cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            except (IndexError, AttributeError):
                raise auth_error("AUTH_CERT_INVALID", "Client certificate missing Common Name in subject")
            
            return AuthResult(
                user_id=subject_cn,
                method=AuthMethod.CERTIFICATE,
                metadata={
                    "subject": cert.subject.rfc4514_string(),
                    "issuer": cert.issuer.rfc4514_string(),
                    "serial_number": str(cert.serial_number),
                    "not_valid_before": cert.not_valid_before_utc.isoformat(),
                    "not_valid_after": cert.not_valid_after_utc.isoformat()
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise auth_error("AUTH_CERT_INVALID", f"Certificate validation failed: {str(e)}")
    
    def _validate_certificate(self, cert: x509.Certificate) -> bool:
        """
        Check certificate validity and trust chain.
        
        Args:
            cert: Certificate to validate
            
        Returns:
            True if certificate is signed by a trusted CA, False otherwise
        """
        if not self.trusted_ca_certs:
            # If no trusted CAs configured, accept all certificates
            return True
        
        # Check if certificate is signed by any of the trusted CAs
        for ca_cert in self.trusted_ca_certs:
            try:
                if cert.issuer == ca_cert.subject:
                    return True
            except Exception:
                continue
        
        return False
    
    async def authenticate_from_header(self, cert_header: Optional[str]) -> AuthResult:
        """
        Authenticate using X-Client-Cert header.
        
        Args:
            cert_header: X-Client-Cert header value (PEM or base64 encoded)
            
        Returns:
            AuthResult with user_id from certificate subject CN
            
        Raises:
            HTTPException: 401 error for missing/invalid headers or certificates
        """
        if not cert_header:
            raise auth_error("AUTH_MISSING", "X-Client-Cert header is missing")
        
        # Try to decode if it's base64 encoded (common in reverse proxy setups)
        cert_pem = cert_header
        if not cert_header.startswith("-----BEGIN CERTIFICATE-----"):
            try:
                cert_pem = base64.b64decode(cert_header).decode('utf-8')
            except Exception:
                pass
        
        return await self.authenticate(cert_pem)


class AuthenticationHandler:
    """Central authentication component that routes requests to appropriate authenticators."""
    
    def __init__(
        self,
        jwt_authenticator: JWTAuthenticator,
        certificate_authenticator: CertificateAuthenticator,
        secret_key_authenticator: SecretKeyAuthenticator
    ):
        self.jwt_authenticator = jwt_authenticator
        self.certificate_authenticator = certificate_authenticator
        self.secret_key_authenticator = secret_key_authenticator
    
    async def authenticate(
        self,
        request: Request,
        method: Optional[AuthMethod] = None,
        authorization: Optional[str] = None,
        x_api_key: Optional[str] = None,
        x_client_cert: Optional[str] = None
    ) -> AuthResult:
        """
        Authenticate the request using the specified or auto-detected method.
        
        Args:
            request: FastAPI request object
            method: Explicit authentication method to use
            authorization: Authorization header value
            x_api_key: X-API-Key header value
            x_client_cert: X-Client-Cert header value
            
        Returns:
            AuthResult from successful authentication
            
        Raises:
            HTTPException: 401/400 error for authentication failures
        """
        # If method is explicitly specified, use only that method
        if method:
            return await self._authenticate_with_method(
                method, authorization, x_api_key, x_client_cert
            )
        
        # Auto-detect authentication method based on provided credentials
        detected_method = self._detect_auth_method(authorization, x_api_key, x_client_cert)
        
        return await self._authenticate_with_method(
            detected_method, authorization, x_api_key, x_client_cert
        )
    
    def _detect_auth_method(
        self,
        authorization: Optional[str],
        x_api_key: Optional[str],
        x_client_cert: Optional[str]
    ) -> AuthMethod:
        """
        Auto-detect authentication method from request headers.
        
        Args:
            authorization: Authorization header value
            x_api_key: X-API-Key header value
            x_client_cert: X-Client-Cert header value
            
        Returns:
            Detected AuthMethod
            
        Raises:
            HTTPException: 400 error for ambiguous or missing credentials
        """
        provided_methods = []
        
        if authorization:
            provided_methods.append(AuthMethod.JWT)
        if x_client_cert:
            provided_methods.append(AuthMethod.CERTIFICATE)
        if x_api_key:
            provided_methods.append(AuthMethod.SECRET_KEY)
        
        if len(provided_methods) == 0:
            raise auth_error("AUTH_MISSING", "No authentication credentials provided")
        
        if len(provided_methods) > 1:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_AMBIGUOUS_AUTH",
                    "message": f"Multiple authentication credentials provided: {', '.join(provided_methods)}. Specify auth_method parameter to choose one."
                }
            )
        
        return provided_methods[0]
    
    async def _authenticate_with_method(
        self,
        method: AuthMethod,
        authorization: Optional[str],
        x_api_key: Optional[str],
        x_client_cert: Optional[str]
    ) -> AuthResult:
        """
        Authenticate using the specified method.
        
        Args:
            method: Authentication method to use
            authorization: Authorization header value
            x_api_key: X-API-Key header value
            x_client_cert: X-Client-Cert header value
            
        Returns:
            AuthResult from successful authentication
            
        Raises:
            HTTPException: 401 error for authentication failures
        """
        if method == AuthMethod.JWT:
            return await self.jwt_authenticator.authenticate_from_header(authorization)
        
        elif method == AuthMethod.CERTIFICATE:
            return await self.certificate_authenticator.authenticate_from_header(x_client_cert)
        
        elif method == AuthMethod.SECRET_KEY:
            return await self.secret_key_authenticator.authenticate_from_header(x_api_key)
        
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_INVALID_AUTH_METHOD",
                    "message": f"Unsupported authentication method: {method}"
                }
            )
    
    def get_supported_methods(self) -> List[AuthMethod]:
        """
        Get list of supported authentication methods.
        
        Returns:
            List of supported AuthMethod values
        """
        return [AuthMethod.JWT, AuthMethod.CERTIFICATE, AuthMethod.SECRET_KEY]
