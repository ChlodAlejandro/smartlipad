"""
SmartLipad Backend - Core Configuration Module
"""
import os
from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str
    DB_NAME: str = "postgres"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    DEBUG: bool = True

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    SCRAPER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_CONCURRENT_REQUESTS: int = 5

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    PROPHET_SEASONALITY_MODE: str = "multiplicative"
    PROPHET_CHANGEPOINT_PRIOR_SCALE: float = 0.05
    FORECAST_HORIZON_DAYS: int = 365

    DATA_PROVIDER: Literal["amadeus", "skyscanner", "offline_csv"] = "amadeus"
    AMADEUS_API_KEY: Optional[str] = None
    AMADEUS_API_SECRET: Optional[str] = None
    AMADEUS_ENVIRONMENT: Literal["test", "production"] = "test"
    SKYSCANNER_API_KEY: Optional[str] = None
    SKYSCANNER_API_HOST: str = "skyscanner-api.p.rapidapi.com"

    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/smartlipad.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
