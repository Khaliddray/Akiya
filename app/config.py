from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # WhatsApp Credentials
    WHATSAPP_TOKEN: str = Field(default="mock_token", description="WhatsApp Cloud API Token")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="mock_phone_id", description="Sender Phone Number ID")
    VERIFY_TOKEN: str = Field(default="monivoice_secret_token", description="Webhook handshake token")

    # N-ATLAS Endpoints
    NATLAS_ASR_URL: str = Field(default="https://api.ncair.gov.ng/v1/asr")
    NATLAS_ASR_KEY: str = Field(default="mock_key")
    NATLAS_LLM_URL: str = Field(default="https://api.ncair.gov.ng/v1/chat/completions")
    NATLAS_LLM_KEY: str = Field(default="mock_key")

    # Storage
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./ledger.db")
    AUDIO_TMP_DIR: str = Field(default="/tmp/monivoice_audio")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
