"""Application configuration loaded from local environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))


def get_cors_origins() -> list[str]:
    """Return the allowed frontend origins, or a development wildcard."""
    origins = os.getenv("CORS_ORIGINS", "*")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]
