import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PORT: int = 8000
    SECRET_KEY: str = "gmail-optimizer-super-secret-key-2026"
    BASE_URL: str = "http://localhost:8000"
    
    # Gmail OAuth
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[str] = None
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/oauth2callback"
    TOKEN_FILE_PATH: str = "token.json"
    CREDENTIALS_FILE_PATH: str = "credentials.json"
    
    # System Controls
    DRY_RUN: bool = True
    AUTO_LABEL: bool = True
    AUTO_ARCHIVE: bool = False
    
    # Confidence thresholds
    CONFIDENCE_AUTO_CLASSIFY: float = 0.90
    CONFIDENCE_FLAG_REVIEW: float = 0.70
    
    # AI Engine
    GEMINI_API_KEY: Optional[str] = None
    
    # Database
    DATABASE_URL: str = "sqlite:///./gmail_intelligence.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
