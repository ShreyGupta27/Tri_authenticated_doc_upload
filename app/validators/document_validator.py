from fastapi import UploadFile, HTTPException
import os

ALLOWED_EXTENSIONS = {
    ".hl7", ".fhir", ".jpg", ".jpeg",
    ".bmp", ".pdf", ".doc", ".docx"
}


class DocumentValidator:
    """Validates uploaded documents against allowed formats."""
    
    def validate(self, file: UploadFile) -> bool:
        """
        Validate file extension against allowed formats.
        
        Args:
            file: The uploaded file to validate
            
        Returns:
            True if valid
            
        Raises:
            HTTPException: 400 error if file extension is not allowed
        """
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_MISSING_FILE",
                    "message": "No filename provided"
                }
            )
        
        extension = self._get_extension(file.filename)
        
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_UNSUPPORTED_FORMAT",
                    "message": f"File extension '{extension}' is not supported. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                }
            )
        
        return True
    
    def _get_extension(self, filename: str) -> str:
        """
        Extract lowercase extension from filename.
        
        Args:
            filename: The filename to extract extension from
            
        Returns:
            Lowercase extension including the dot (e.g., '.pdf')
        """
        _, ext = os.path.splitext(filename)
        return ext.lower()
    
    def is_valid_extension(self, filename: str) -> bool:
        """
        Check if filename has a valid extension without raising exception.
        
        Args:
            filename: The filename to check
            
        Returns:
            True if extension is valid, False otherwise
        """
        if not filename:
            return False
        extension = self._get_extension(filename)
        return extension in ALLOWED_EXTENSIONS
