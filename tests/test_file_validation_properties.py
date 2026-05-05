"""
Property-based tests for file extension validation.

Feature: document-upload-auth, Property 1: File Extension Validation
Validates: Requirements 1.1, 1.2, 1.4
"""
import pytest
from hypothesis import given, strategies as st, settings
from fastapi import HTTPException

from app.validators.document_validator import DocumentValidator, ALLOWED_EXTENSIONS


# Strategies for generating test data
allowed_extensions = list(ALLOWED_EXTENSIONS)

# Generate filenames with allowed extensions (various cases)
@st.composite
def valid_filename_strategy(draw):
    """Generate filenames with allowed extensions in various cases."""
    base_name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
        min_size=1,
        max_size=50
    ))
    ext = draw(st.sampled_from(allowed_extensions))
    # Randomly change case of extension
    case_variant = draw(st.sampled_from(['lower', 'upper', 'mixed']))
    if case_variant == 'upper':
        ext = ext.upper()
    elif case_variant == 'mixed':
        ext = ''.join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(ext))
    return base_name + ext


# Generate filenames with disallowed extensions
disallowed_extensions = ['.exe', '.bat', '.sh', '.py', '.js', '.html', '.css', '.txt', '.xml', '.json', '.zip', '.tar', '.gz']

@st.composite
def invalid_filename_strategy(draw):
    """Generate filenames with disallowed extensions."""
    base_name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
        min_size=1,
        max_size=50
    ))
    ext = draw(st.sampled_from(disallowed_extensions))
    return base_name + ext


class MockUploadFile:
    """Mock UploadFile for testing."""
    def __init__(self, filename: str):
        self.filename = filename


class TestFileExtensionValidationProperty:
    """
    Property 1: File Extension Validation
    
    For any filename with an extension in the allowed set regardless of case,
    the Document_Validator SHALL accept the file. For any filename with an
    extension NOT in the allowed set, the Document_Validator SHALL reject
    with a 400 error.
    
    Validates: Requirements 1.1, 1.2, 1.4
    """
    
    @given(filename=valid_filename_strategy())
    @settings(max_examples=100)
    def test_valid_extensions_accepted(self, filename: str):
        """
        Feature: document-upload-auth, Property 1: File Extension Validation
        
        For any filename with an allowed extension (case-insensitive),
        validation should succeed.
        """
        validator = DocumentValidator()
        mock_file = MockUploadFile(filename)
        
        # Should not raise exception
        result = validator.validate(mock_file)
        assert result is True
    
    @given(filename=invalid_filename_strategy())
    @settings(max_examples=100)
    def test_invalid_extensions_rejected(self, filename: str):
        """
        Feature: document-upload-auth, Property 1: File Extension Validation
        
        For any filename with a disallowed extension,
        validation should raise HTTPException with 400 status.
        """
        validator = DocumentValidator()
        mock_file = MockUploadFile(filename)
        
        with pytest.raises(HTTPException) as exc_info:
            validator.validate(mock_file)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == "VALIDATION_UNSUPPORTED_FORMAT"
    
    @given(ext=st.sampled_from(allowed_extensions))
    @settings(max_examples=100)
    def test_case_insensitive_validation(self, ext: str):
        """
        Feature: document-upload-auth, Property 1: File Extension Validation
        
        For any allowed extension, both uppercase and lowercase versions
        should be accepted.
        """
        validator = DocumentValidator()
        
        # Test lowercase
        lower_file = MockUploadFile(f"document{ext.lower()}")
        assert validator.validate(lower_file) is True
        
        # Test uppercase
        upper_file = MockUploadFile(f"document{ext.upper()}")
        assert validator.validate(upper_file) is True
