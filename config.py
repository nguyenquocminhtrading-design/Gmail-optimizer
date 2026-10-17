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
    
    # AI Engine — Gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_MODELS: str = "gemini-3.6-flash,gemini-1.5-flash,gemini-1.5-flash-8b"

    # AI Engine — Groq Cloud (OpenAI-compatible, https://api.groq.com/openai/v1)
    # API keys are read from .env only — NEVER hardcode them in source code.
    GROQ_API_KEY: Optional[str] = None
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    # Comma-separated list of Groq text models tried in order as fallback
    GROQ_TEXT_MODELS: str = "llama-3.1-70b-versatile,llama-3.1-8b-instant,mixtral-8x7b-32768"

    # Groq Speech-to-Text (Whisper)
    GROQ_STT_ENABLED: bool = False
    GROQ_STT_MODEL: str = "whisper-large-v3-turbo"

    # Groq Text-to-Speech (Orpheus)
    GROQ_TTS_ENABLED: bool = False
    GROQ_TTS_MODEL: str = "canopylabs/orpheus-v1-english"

    # AI Engine — Ollama local
    OLLAMA_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3.5:2b"
    
    # Database
    DATABASE_URL: str = "sqlite:///./gmail_intelligence.db"

    # Sync Settings
    SYNC_MAX_EMAILS: int = 0  # Max emails to fetch per sync (0 = unlimited)

    # Daily Digest / Notifications
    DAILY_DIGEST_ENABLED: bool = True
    DAILY_DIGEST_HOUR: int = 7          # Hour to send digest (24h format, local time)
    # Telegram Notifications
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
