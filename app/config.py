import os
import secrets
from pydantic import BaseModel, Field

class Settings(BaseModel):
    PROJECT_NAME: str = "Permission-Aware Multi-Tenant Healthcare RAG"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Database connection string
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+psycopg2://localhost/multitenant_rag"
    )
    
    # JWT security settings
    JWT_SECRET: str = os.getenv("JWT_SECRET") or secrets.token_hex(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    # Embedding settings
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384
    
    # Retrieval defaults
    DEFAULT_TOP_K: int = 5

    # Development token minting and synthetic seeding require explicit opt-in.
    ALLOW_DEVELOPMENT_ENDPOINTS: bool = os.getenv("ALLOW_DEVELOPMENT_ENDPOINTS", "false").lower() == "true"

settings = Settings()

if settings.ENVIRONMENT == "production" and len(os.getenv("JWT_SECRET", "")) < 32:
    raise ValueError("Production requires JWT_SECRET with at least 32 characters")
