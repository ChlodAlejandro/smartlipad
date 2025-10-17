"""
SmartLipad Backend - Pydantic Schemas for Request/Response Validation
"""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ==================== User Schemas ====================

class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user creation"""
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Schema for user response"""
    user_id: int
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data"""
    user_id: Optional[int] = None
    email: Optional[str] = None


# ==================== Airport & Airline Schemas ====================

class AirportBase(BaseModel):
    """Base airport schema"""
    iata_code: str = Field(..., max_length=3)
    name: str
    city: str
    country: str


class AirportResponse(AirportBase):
    """Airport response schema"""
    airport_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class AirlineBase(BaseModel):
    """Base airline schema"""
    iata_code: str = Field(..., max_length=3)
    name: str
    country: Optional[str] = None


class AirlineResponse(AirlineBase):
    """Airline response schema"""
    airline_id: int
    active: bool
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Route Schemas ====================

class RouteBase(BaseModel):
    """Base route schema"""
    origin_airport_id: int
    destination_airport_id: int
    is_domestic: bool


class RouteResponse(RouteBase):
    """Route response schema"""
    route_id: int
    distance_km: Optional[int] = None
    active: bool
    origin_airport: Optional[AirportResponse] = None
    destination_airport: Optional[AirportResponse] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Fare Schemas ====================

class FareSnapshotBase(BaseModel):
    """Base fare snapshot schema"""
    route_id: int
    departure_date: date
    price_amount: float
    currency_code: str


class FareSnapshotResponse(FareSnapshotBase):
    """Fare snapshot response schema"""
    fare_snapshot_id: int
    airline_id: Optional[int] = None
    scrape_timestamp: datetime
    cabin_class: Optional[str] = None
    fare_type: Optional[str] = None
    seats_remaining: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class FareSearchRequest(BaseModel):
    """Search fares request schema"""
    origin_iata: str = Field(..., max_length=3)
    destination_iata: str = Field(..., max_length=3)
    departure_date: Optional[date] = None
    limit: int = Field(default=20, ge=1, le=100)


class FareSearchResponse(BaseModel):
    """Search fares response schema"""
    route: RouteResponse
    fares: List[FareSnapshotResponse]
    total_count: int


# ==================== Forecast Schemas ====================

class ForecastRequest(BaseModel):
    """Forecast request schema"""
    origin_iata: str = Field(..., max_length=3)
    destination_iata: str = Field(..., max_length=3)
    forecast_months: int = Field(default=12, ge=1, le=24)


class ForecastResultResponse(BaseModel):
    """Forecast result response schema"""
    forecast_result_id: int
    route_id: int
    target_period_start: date
    target_period_end: date
    point_forecast: float
    lower_ci: Optional[float] = None
    upper_ci: Optional[float] = None
    currency_code: str
    is_cheapest_flag: bool
    
    model_config = ConfigDict(from_attributes=True)


class ForecastResponse(BaseModel):
    """Forecast response with insights"""
    route: RouteResponse
    forecasts: List[ForecastResultResponse]
    best_month: Optional[ForecastResultResponse] = None
    worst_month: Optional[ForecastResultResponse] = None
    average_fare: Optional[float] = None
    forecast_run_id: int


class MonthlyForecastSummary(BaseModel):
    """Monthly forecast summary"""
    month: str  # YYYY-MM format
    average_fare: float
    min_fare: float
    max_fare: float
    currency_code: str
    percent_vs_peak: Optional[float] = None


# ==================== Comparison Schemas ====================

class ComparisonRequest(BaseModel):
    """Fare comparison request"""
    origin_iata: str = Field(..., max_length=3)
    destination_iata: str = Field(..., max_length=3)
    months: List[str] = Field(..., min_length=2, max_length=12)  # YYYY-MM format
    save_comparison: bool = False


class ComparisonResponse(BaseModel):
    """Comparison response schema"""
    route: RouteResponse
    monthly_comparisons: List[MonthlyForecastSummary]
    cheapest_month: MonthlyForecastSummary
    most_expensive_month: MonthlyForecastSummary
    potential_savings: float
    savings_percentage: float


# ==================== Admin Schemas ====================

class ScrapeJobResponse(BaseModel):
    """Scrape job response"""
    job_id: int
    source_id: int
    status: str
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total_attempted: int
    total_captured: int
    total_errors: int
    
    model_config = ConfigDict(from_attributes=True)


class ForecastRunResponse(BaseModel):
    """Forecast run response"""
    forecast_run_id: int
    model_name: str
    run_scope: str
    status: str
    train_start_date: date
    train_end_date: date
    horizon_days: int
    created_at: datetime
    finished_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Generic Responses ====================

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response schema"""
    detail: str
    error_code: Optional[str] = None
