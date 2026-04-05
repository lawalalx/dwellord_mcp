
from pydantic import Field, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    # ---------- General ----------
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    
    OPENAI_API_KEY: str = Field(..., validation_alias="OPENAI_API_KEY")
    GROQ_API_KEY: str  = Field(..., validation_alias="GROQ_API_KEY")
    
    # ---------- Optional ----------
    REDIS_URL: str | None = None
    DATABASE_URL: str | None = None
    MCP_SSE_URL: str | None = None
    MCP_SSE_PORT: int | None = 3001
    SENSITIVE_DATA_SECRET: str | None = None
    

    # THIS IS THE KEY FIX
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="allow",
    )


settings = Settings()
