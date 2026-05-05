from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # JWT Settings
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    
    # Certificate Settings
    trusted_ca_certs_path: str = ""
    
    # API Key Settings - comma-separated key:app_name pairs (fallback for testing)
    api_keys: str = "test-key-1:app1,test-key-2:app2"
    
    # Database Settings
    database_url: str = "postgresql://localhost:5432/jonda_db"
    
    # GCS Settings
    gcs_bucket_name: str = "document-upload-bucket"
    google_application_credentials: Optional[str] = None
    
    class Config:
        env_file = ".env"
        extra = "ignore"
    
    def get_api_keys_dict(self) -> dict[str, str]:
        """Parse api_keys string into dictionary (fallback for testing)."""
        if not self.api_keys:
            return {}
        result = {}
        for pair in self.api_keys.split(","):
            if ":" in pair:
                key, app_name = pair.split(":", 1)
                result[key.strip()] = app_name.strip()
        return result
    
    def setup_gcs_credentials(self):
        """Set up Google Cloud credentials environment variable."""
        if self.google_application_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.google_application_credentials


settings = Settings()
# Set up GCS credentials when settings are loaded
settings.setup_gcs_credentials()
