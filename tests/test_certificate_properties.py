"""
Property-based tests for certificate authentication.

Feature: document-upload-auth, Properties 6-8: Certificate Authentication
Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from fastapi import HTTPException
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timezone, timedelta
import base64

from app.auth.certificate_authenticator import CertificateAuthenticator
from app.models import AuthMethod


# Generate test CA and certificates
def generate_ca_certificate():
    """Generate a test CA certificate."""
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Test State"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Test City"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Test CA"),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True,
    ).sign(private_key, hashes.SHA256())
    
    return cert, private_key


def generate_client_certificate(ca_cert, ca_private_key, common_name: str, 
                              not_valid_before: datetime = None,
                              not_valid_after: datetime = None):
    """Generate a client certificate signed by the CA."""
    # Generate private key for client
    client_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Create subject with provided common name
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Test State"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Test City"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Client"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    
    # Set validity dates
    if not_valid_before is None:
        not_valid_before = datetime.now(timezone.utc)
    if not_valid_after is None:
        not_valid_after = datetime.now(timezone.utc) + timedelta(days=30)
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        client_private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        not_valid_before
    ).not_valid_after(
        not_valid_after
    ).sign(ca_private_key, hashes.SHA256())
    
    return cert, client_private_key


def generate_self_signed_certificate(common_name: str):
    """Generate a self-signed certificate (untrusted)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=30)
    ).sign(private_key, hashes.SHA256())
    
    return cert, private_key


# Generate test CA once
TEST_CA_CERT, TEST_CA_PRIVATE_KEY = generate_ca_certificate()
TEST_CA_PEM = TEST_CA_CERT.public_bytes(serialization.Encoding.PEM).decode()


# Strategies for generating test data
@st.composite
def valid_common_name_strategy(draw):
    """Generate valid common names for certificates."""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N')),
        min_size=1,
        max_size=16  # Further reduced to avoid UTF-8 encoding issues
    ))


@st.composite
def valid_certificate_strategy(draw):
    """Generate valid client certificates signed by test CA."""
    common_name = draw(valid_common_name_strategy())
    cert, _ = generate_client_certificate(TEST_CA_CERT, TEST_CA_PRIVATE_KEY, common_name)
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    return cert_pem, common_name


@st.composite
def expired_certificate_strategy(draw):
    """Generate expired client certificates."""
    common_name = draw(valid_common_name_strategy())
    
    # Create certificate that expired in the past
    not_valid_before = datetime.now(timezone.utc) - timedelta(days=60)
    not_valid_after = datetime.now(timezone.utc) - timedelta(days=draw(st.integers(min_value=1, max_value=30)))
    
    cert, _ = generate_client_certificate(
        TEST_CA_CERT, TEST_CA_PRIVATE_KEY, common_name,
        not_valid_before, not_valid_after
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    return cert_pem, common_name


@st.composite
def untrusted_certificate_strategy(draw):
    """Generate self-signed (untrusted) certificates."""
    common_name = draw(valid_common_name_strategy())
    cert, _ = generate_self_signed_certificate(common_name)
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    return cert_pem, common_name


class TestCertificateAuthenticationProperties:
    """
    Properties 6-8: Certificate Authentication
    
    Property 6: Certificate Valid Authentication
    Property 7: Certificate Expired Rejection
    Property 8: Certificate Untrusted Rejection
    
    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """
    
    @given(cert_data=valid_certificate_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    async def test_valid_certificate_authentication(self, cert_data):
        """
        Feature: document-upload-auth, Property 6: Certificate Valid Authentication
        
        For any valid client certificate (not expired, signed by trusted CA)
        with a subject CN, the Certificate_Authenticator SHALL return an AuthResult
        with user_id matching the certificate's subject CN.
        """
        cert_pem, expected_cn = cert_data
        authenticator = CertificateAuthenticator([TEST_CA_PEM])
        
        # Should authenticate successfully
        result = await authenticator.authenticate(cert_pem)
        
        assert result.user_id == expected_cn
        assert result.method == AuthMethod.CERTIFICATE
        assert "subject" in result.metadata
        assert "issuer" in result.metadata
    
    @given(cert_data=expired_certificate_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    async def test_expired_certificate_rejection(self, cert_data):
        """
        Feature: document-upload-auth, Property 7: Certificate Expired Rejection
        
        For any client certificate with a notAfter date in the past,
        the Certificate_Authenticator SHALL reject with a 401 Unauthorized error.
        """
        cert_pem, _ = cert_data
        authenticator = CertificateAuthenticator([TEST_CA_PEM])
        
        # Should raise HTTPException with 401 status
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate(cert_pem)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_CERT_EXPIRED"
    
    @given(cert_data=untrusted_certificate_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    async def test_untrusted_certificate_rejection(self, cert_data):
        """
        Feature: document-upload-auth, Property 8: Certificate Untrusted Rejection
        
        For any client certificate not signed by a trusted CA,
        the Certificate_Authenticator SHALL reject with a 401 Unauthorized error.
        """
        cert_pem, _ = cert_data
        authenticator = CertificateAuthenticator([TEST_CA_PEM])
        
        # Should raise HTTPException with 401 status
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate(cert_pem)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_CERT_UNTRUSTED"
    
    @given(cert_data=valid_certificate_strategy())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    async def test_base64_encoded_certificate_header(self, cert_data):
        """
        Feature: document-upload-auth, Property 6: Certificate Valid Authentication
        
        For any valid certificate provided as base64-encoded in header,
        the Certificate_Authenticator SHALL decode and validate correctly.
        """
        cert_pem, expected_cn = cert_data
        authenticator = CertificateAuthenticator([TEST_CA_PEM])
        
        # Encode certificate as base64
        cert_b64 = base64.b64encode(cert_pem.encode()).decode()
        
        # Should authenticate successfully
        result = await authenticator.authenticate_from_header(cert_b64)
        
        assert result.user_id == expected_cn
        assert result.method == AuthMethod.CERTIFICATE
    
    @given(cert_data=valid_certificate_strategy())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    async def test_pem_certificate_header(self, cert_data):
        """
        Feature: document-upload-auth, Property 6: Certificate Valid Authentication
        
        For any valid certificate provided as PEM in header,
        the Certificate_Authenticator SHALL validate correctly.
        """
        cert_pem, expected_cn = cert_data
        authenticator = CertificateAuthenticator([TEST_CA_PEM])
        
        # Should authenticate successfully with PEM format
        result = await authenticator.authenticate_from_header(cert_pem)
        
        assert result.user_id == expected_cn
        assert result.method == AuthMethod.CERTIFICATE