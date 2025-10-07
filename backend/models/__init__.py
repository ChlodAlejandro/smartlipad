"""
SmartLipad Backend - Database Models
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Boolean, TIMESTAMP, Text, Date, 
    DECIMAL, ForeignKey, CheckConstraint, UniqueConstraint, Index, JSON, CHAR
)
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    """User account model"""
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120))
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)
    
    # Relationships
    roles = relationship("Role", secondary="user_role_map", back_populates="users")
    comparisons = relationship("UserComparison", back_populates="user", cascade="all, delete-orphan")
    forecast_runs = relationship("ForecastRun", back_populates="user")


class Role(Base):
    """User role model"""
    __tablename__ = "roles"
    
    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(40), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    users = relationship("User", secondary="user_role_map", back_populates="roles")


class UserRoleMap(Base):
    """User-Role mapping table"""
    __tablename__ = "user_role_map"
    
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True)
    assigned_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)


class Airline(Base):
    """Airline model"""
    __tablename__ = "airlines"
    
    airline_id = Column(Integer, primary_key=True, autoincrement=True)
    iata_code = Column(String(3), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    country = Column(String(80))
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)
    
    # Relationships
    fare_snapshots = relationship("FareSnapshot", back_populates="airline")


class Airport(Base):
    """Airport model"""
    __tablename__ = "airports"
    
    airport_id = Column(Integer, primary_key=True, autoincrement=True)
    iata_code = Column(String(3), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    country = Column(String(80), nullable=False, index=True)
    latitude = Column(DECIMAL(9, 6))
    longitude = Column(DECIMAL(9, 6))
    timezone = Column(String(60))
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)
    
    # Relationships
    origin_routes = relationship("Route", foreign_keys="Route.origin_airport_id", back_populates="origin_airport")
    destination_routes = relationship("Route", foreign_keys="Route.destination_airport_id", back_populates="destination_airport")


class Route(Base):
    """Route model"""
    __tablename__ = "routes"
    __table_args__ = (
        UniqueConstraint("origin_airport_id", "destination_airport_id", name="ux_routes_origin_dest"),
        CheckConstraint("origin_airport_id <> destination_airport_id"),
    )
    
    route_id = Column(Integer, primary_key=True, autoincrement=True)
    origin_airport_id = Column(Integer, ForeignKey("airports.airport_id", ondelete="RESTRICT"), nullable=False)
    destination_airport_id = Column(Integer, ForeignKey("airports.airport_id", ondelete="RESTRICT"), nullable=False)
    distance_km = Column(Integer)
    is_domestic = Column(Boolean, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    origin_airport = relationship("Airport", foreign_keys=[origin_airport_id], back_populates="origin_routes")
    destination_airport = relationship("Airport", foreign_keys=[destination_airport_id], back_populates="destination_routes")
    fare_snapshots = relationship("FareSnapshot", back_populates="route")
    forecast_results = relationship("ForecastResult", back_populates="route")
    monthly_lowest_fares = relationship("MonthlyLowestFare", back_populates="route")
    user_comparisons = relationship("UserComparison", back_populates="route")


class Currency(Base):
    """Currency model"""
    __tablename__ = "currencies"
    
    currency_code = Column(CHAR(3), primary_key=True)
    name = Column(String(50), nullable=False)
    symbol = Column(String(5))
    
    # Relationships
    fare_snapshots = relationship("FareSnapshot", back_populates="currency")
    forecast_results = relationship("ForecastResult", back_populates="currency")
    monthly_lowest_fares = relationship("MonthlyLowestFare", back_populates="currency")


class DataSource(Base):
    """Data source model for scrapers and APIs"""
    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint("type IN ('scraper','api')"),
    )
    
    source_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), unique=True, nullable=False)
    type = Column(String(30), nullable=False)  # 'scraper' or 'api'
    base_url = Column(Text)
    terms_version = Column(String(50))
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)
    
    # Relationships
    scrape_jobs = relationship("ScrapeJob", back_populates="source")
    fare_snapshots = relationship("FareSnapshot", back_populates="source")


class ScrapeJob(Base):
    """Scrape job model"""
    __tablename__ = "scrape_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','success','failed','partial')"),
    )
    
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(20), nullable=False)
    scheduled_at = Column(TIMESTAMP, nullable=False)
    started_at = Column(TIMESTAMP)
    finished_at = Column(TIMESTAMP)
    total_attempted = Column(Integer, nullable=False, default=0)
    total_captured = Column(Integer, nullable=False, default=0)
    total_errors = Column(Integer, nullable=False, default=0)
    error_message = Column(Text)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    source = relationship("DataSource", back_populates="scrape_jobs")
    logs = relationship("ScrapeJobLog", back_populates="job", cascade="all, delete-orphan")


class ScrapeJobLog(Base):
    """Scrape job log model"""
    __tablename__ = "scrape_job_logs"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("scrape_jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = Column(Integer, ForeignKey("routes.route_id", ondelete="SET NULL"), index=True)
    url = Column(Text)
    http_status = Column(Integer)
    success = Column(Boolean, nullable=False, index=True)
    message = Column(Text)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    job = relationship("ScrapeJob", back_populates="logs")


class FareSnapshot(Base):
    """Fare snapshot model - stores scraped fare data"""
    __tablename__ = "fare_snapshots"
    __table_args__ = (
        UniqueConstraint("hash_signature", name="ux_fare_snapshots_hash"),
        CheckConstraint("price_amount >= 0"),
        Index("idx_fares_route_dep", "route_id", "departure_date"),
        Index("idx_fares_scrape_ts", "scrape_timestamp"),
        Index("idx_fares_route_airline", "route_id", "airline_id"),
    )
    
    fare_snapshot_id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.route_id", ondelete="RESTRICT"), nullable=False)
    airline_id = Column(Integer, ForeignKey("airlines.airline_id", ondelete="SET NULL"))
    source_id = Column(Integer, ForeignKey("data_sources.source_id", ondelete="RESTRICT"), nullable=False)
    departure_date = Column(Date, nullable=False)
    scrape_timestamp = Column(TIMESTAMP, nullable=False)
    price_amount = Column(DECIMAL(10, 2), nullable=False)
    currency_code = Column(CHAR(3), ForeignKey("currencies.currency_code", ondelete="RESTRICT"), nullable=False)
    cabin_class = Column(String(20))
    fare_type = Column(String(30))
    seats_remaining = Column(Integer)
    hash_signature = Column(CHAR(64), nullable=False)
    is_valid = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    route = relationship("Route", back_populates="fare_snapshots")
    airline = relationship("Airline", back_populates="fare_snapshots")
    source = relationship("DataSource", back_populates="fare_snapshots")
    currency = relationship("Currency", back_populates="fare_snapshots")


class ForecastRun(Base):
    """Forecast run model"""
    __tablename__ = "forecast_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running','success','failed','partial')"),
        CheckConstraint("train_start_date <= train_end_date"),
        CheckConstraint("horizon_days > 0"),
    )
    
    forecast_run_id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(40), nullable=False)
    run_scope = Column(String(20), nullable=False)  # 'all_routes', 'single_route', 'subset'
    initiated_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    status = Column(String(20), nullable=False)
    train_start_date = Column(Date, nullable=False)
    train_end_date = Column(Date, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    seasonalities = Column(JSON)
    metrics_json = Column(JSON)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    finished_at = Column(TIMESTAMP)
    
    # Relationships
    user = relationship("User", back_populates="forecast_runs")
    results = relationship("ForecastResult", back_populates="forecast_run", cascade="all, delete-orphan")
    model_parameters = relationship("ModelParameter", back_populates="forecast_run", uselist=False, cascade="all, delete-orphan")


class ModelParameter(Base):
    """Model parameters for reproducibility"""
    __tablename__ = "model_parameters"
    
    model_param_id = Column(Integer, primary_key=True, autoincrement=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.forecast_run_id", ondelete="CASCADE"), unique=True, nullable=False)
    raw_params_json = Column(JSON, nullable=False)
    feature_list = Column(JSON)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    forecast_run = relationship("ForecastRun", back_populates="model_parameters")


class ForecastResult(Base):
    """Forecast result model"""
    __tablename__ = "forecast_results"
    __table_args__ = (
        CheckConstraint("target_period_start <= target_period_end"),
        CheckConstraint("point_forecast >= 0"),
        Index("idx_forecast_route_period", "route_id", "target_period_start"),
        Index("idx_forecast_route_price", "route_id", "point_forecast"),
        Index("idx_forecast_run", "forecast_run_id"),
    )
    
    forecast_result_id = Column(Integer, primary_key=True, autoincrement=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.forecast_run_id", ondelete="CASCADE"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.route_id", ondelete="RESTRICT"), nullable=False)
    target_period_start = Column(Date, nullable=False)
    target_period_end = Column(Date, nullable=False)
    point_forecast = Column(DECIMAL(10, 2), nullable=False)
    lower_ci = Column(DECIMAL(10, 2))
    upper_ci = Column(DECIMAL(10, 2))
    currency_code = Column(CHAR(3), ForeignKey("currencies.currency_code", ondelete="RESTRICT"), nullable=False)
    model_version = Column(String(20))
    is_cheapest_flag = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    forecast_run = relationship("ForecastRun", back_populates="results")
    route = relationship("Route", back_populates="forecast_results")
    currency = relationship("Currency", back_populates="forecast_results")


class MonthlyLowestFare(Base):
    """Monthly lowest fare model - historical minimums"""
    __tablename__ = "monthly_lowest_fares"
    __table_args__ = (
        CheckConstraint("observed_min_price >= 0"),
        CheckConstraint("sample_size >= 0"),
        Index("idx_mlf_currency", "currency_code"),
    )
    
    route_id = Column(Integer, ForeignKey("routes.route_id", ondelete="RESTRICT"), primary_key=True)
    month_start = Column(Date, primary_key=True)
    observed_min_price = Column(DECIMAL(10, 2), nullable=False)
    currency_code = Column(CHAR(3), ForeignKey("currencies.currency_code", ondelete="RESTRICT"), nullable=False)
    sample_size = Column(Integer, nullable=False)
    last_computed_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    route = relationship("Route", back_populates="monthly_lowest_fares")
    currency = relationship("Currency", back_populates="monthly_lowest_fares")


class UserComparison(Base):
    """User comparison model - saved fare comparisons"""
    __tablename__ = "user_comparisons"
    __table_args__ = (
        CheckConstraint("JSON_VALID(months_compared)"),
    )
    
    comparison_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.route_id", ondelete="RESTRICT"), nullable=False)
    months_compared = Column(JSON, nullable=False)  # Array of 'YYYY-MM' strings
    notes = Column(Text)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="comparisons")
    route = relationship("Route", back_populates="user_comparisons")


class APIRequestLog(Base):
    """API request log model"""
    __tablename__ = "api_request_logs"
    
    api_log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    endpoint = Column(String(200), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    response_status = Column(Integer, nullable=False)
    latency_ms = Column(Integer)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, index=True)


class ETLJobRun(Base):
    """ETL job run model"""
    __tablename__ = "etl_job_runs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','success','failed','partial')"),
    )
    
    etl_job_id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    started_at = Column(TIMESTAMP)
    finished_at = Column(TIMESTAMP)
    message = Column(Text)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
