"""
SmartLipad Backend - Core Configuration Module
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "smartlipad_user"
    DB_PASSWORD: str
    DB_NAME: str = "smartlipad_db"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Scraping
    SCRAPER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_CONCURRENT_REQUESTS: int = 5
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Forecasting
    PROPHET_SEASONALITY_MODE: str = "multiplicative"
    PROPHET_CHANGEPOINT_PRIOR_SCALE: float = 0.05
    FORECAST_HORIZON_DAYS: int = 365
    
    # External APIs
    SKYSCANNER_API_KEY: Optional[str] = None
    SKYSCANNER_API_HOST: str = "skyscanner-api.p.rapidapi.com"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/smartlipad.log"
    
    @property
    def database_url(self) -> str:
        """Construct database URL"""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
