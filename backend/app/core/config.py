import os
from typing import List, Union
from pydantic import AnyHttpUrl, BeforeValidator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated

def parse_cors(v: Union[str, List[str]]) -> List[str]:
    if isinstance(v, str):
        # Handle comma-separated string
        if "," in v:
            return [i.strip() for i in v.split(",")]
        # Handle single URL string
        return [v.strip()]
    elif isinstance(v, list):
        return v
    return []

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ReviewPilot"

    # CORS Origins
    BACKEND_CORS_ORIGINS: Annotated[
        List[str], BeforeValidator(parse_cors)
    ] = ["http://localhost:3000", "http://localhost:8000"]

    # Security
    JWT_SECRET_KEY: str = "supersecretjwtkeyforreviewpilotdevelopmentonlychangeinprod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ENCRYPTION_KEY: str = "g-m9F_XfV3r4Gg1y7pL2d2uQpA6b5D1n8U3i4N2o5E8="  # 32-byte URL-safe base64-encoded key

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "reviewpilot"
    
    # We will derive the async and sync URIs dynamically if not directly provided
    SQLALCHEMY_DATABASE_URI: str | None = None
    SQLALCHEMY_SYNC_DATABASE_URI: str | None = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, info) -> str:
        if isinstance(v, str) and v:
            return v
        data = info.data
        return f"postgresql+asyncpg://{data.get('POSTGRES_USER')}:{data.get('POSTGRES_PASSWORD')}@{data.get('POSTGRES_SERVER')}:{data.get('POSTGRES_PORT')}/{data.get('POSTGRES_DB')}"

    @field_validator("SQLALCHEMY_SYNC_DATABASE_URI", mode="before")
    @classmethod
    def assemble_sync_db_connection(cls, v: str | None, info) -> str:
        if isinstance(v, str) and v:
            return v
        data = info.data
        return f"postgresql://{data.get('POSTGRES_USER')}:{data.get('POSTGRES_PASSWORD')}@{data.get('POSTGRES_SERVER')}:{data.get('POSTGRES_PORT')}/{data.get('POSTGRES_DB')}"

    # GitHub OAuth & Integration
    GITHUB_CLIENT_ID: str = "mock_client_id"
    GITHUB_CLIENT_SECRET: str = "mock_client_secret"
    GITHUB_APP_ID: str = "mock_app_id"
    GITHUB_WEBHOOK_SECRET: str = "mock_webhook_secret"
    GITHUB_PRIVATE_KEY: str = "mock_private_key"

    # Vector DB & Embeddings
    QDRANT_URL: str = "in-memory"
    QDRANT_API_KEY: str | None = None

    # AI Reviews
    GROQ_API_KEY: str = "mock_groq_api_key"
    GROQ_MODEL: str = "llama3-70b-8192"

settings = Settings()
