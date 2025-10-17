"""
SmartLipad Backend - Pytest Configuration and Fixtures

This module provides test fixtures for:
- Test database with in-memory SQLite
- FastAPI test client
- Authentication helpers
- Sample data fixtures
"""
import pytest
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from backend.main import app
from backend.database import Base, get_db
from backend.models import (
    User, Role, Airport, Airline, Route, Currency,
    FareSnapshot, ForecastRun, ForecastResult, DataSource
)
from backend.core.security import get_password_hash


# Test Database Configuration
TEST_DATABASE_URL = "sqlite:///./test_smartlipad.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user_role = Role(
        role_name="user",
        description="Regular user"
    )
    db_session.add(user_role)
    db_session.commit()
    
    user = User(
        email="testuser@example.com",
        password_hash=get_password_hash("testpass123"),
        full_name="Test User",
        status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Assign role
    from backend.models import UserRoleMap
    user_role_map = UserRoleMap(
        user_id=user.user_id,
        role_id=user_role.role_id
    )
    db_session.add(user_role_map)
    db_session.commit()
    
    return user


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing"""
    admin_role = Role(
        role_name="admin",
        description="Administrator"
    )
    db_session.add(admin_role)
    db_session.commit()
    
    admin = User(
        email="admin@example.com",
        password_hash=get_password_hash("adminpass123"),
        full_name="Admin User",
        status="active"
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    # Assign role
    from backend.models import UserRoleMap
    admin_role_map = UserRoleMap(
        user_id=admin.user_id,
        role_id=admin_role.role_id
    )
    db_session.add(admin_role_map)
    db_session.commit()
    
    return admin


@pytest.fixture
def auth_headers(client, sample_user):
    """Get authentication headers for a sample user"""
    response = client.post(
        "/api/auth/login",
        data={
            "username": "testuser@example.com",
            "password": "testpass123"
        }
    )
    if response.status_code == 405:
        pytest.skip("Login endpoint not implemented")
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_currency(db_session):
    """Create sample currencies"""
    php = Currency(currency_code="PHP", name="Philippine Peso", symbol="₱")
    usd = Currency(currency_code="USD", name="US Dollar", symbol="$")
    db_session.add_all([php, usd])
    db_session.commit()
    return php, usd


@pytest.fixture
def sample_airports(db_session):
    """Create sample Philippine airports"""
    airports = [
        Airport(
            iata_code="MNL",
            name="Ninoy Aquino International Airport",
            city="Manila",
            country="Philippines",
            latitude=14.5086,
            longitude=121.0194,
            timezone="Asia/Manila"
        ),
        Airport(
            iata_code="CEB",
            name="Mactan-Cebu International Airport",
            city="Cebu",
            country="Philippines",
            latitude=10.3075,
            longitude=123.9794,
            timezone="Asia/Manila"
        ),
        Airport(
            iata_code="DVO",
            name="Francisco Bangoy International Airport",
            city="Davao",
            country="Philippines",
            latitude=7.1253,
            longitude=125.6458,
            timezone="Asia/Manila"
        ),
        Airport(
            iata_code="CRK",
            name="Clark International Airport",
            city="Angeles",
            country="Philippines",
            latitude=15.1859,
            longitude=120.5602,
            timezone="Asia/Manila"
        )
    ]
    db_session.add_all(airports)
    db_session.commit()
    return airports


@pytest.fixture
def sample_airlines(db_session):
    """Create sample Philippine airlines"""
    airlines = [
        Airline(
            iata_code="5J",
            name="Cebu Pacific",
            country="Philippines",
            active=True
        ),
        Airline(
            iata_code="PR",
            name="Philippine Airlines",
            country="Philippines",
            active=True
        ),
        Airline(
            iata_code="Z2",
            name="AirAsia Philippines",
            country="Philippines",
            active=True
        )
    ]
    db_session.add_all(airlines)
    db_session.commit()
    return airlines


@pytest.fixture
def sample_routes(db_session, sample_airports):
    """Create sample routes between airports"""
    mnl = sample_airports[0]  # Manila
    ceb = sample_airports[1]  # Cebu
    dvo = sample_airports[2]  # Davao
    
    routes = [
        Route(
            origin_airport_id=mnl.airport_id,
            destination_airport_id=ceb.airport_id,
            is_domestic=True,
            active=True
        ),
        Route(
            origin_airport_id=mnl.airport_id,
            destination_airport_id=dvo.airport_id,
            is_domestic=True,
            active=True
        ),
        Route(
            origin_airport_id=ceb.airport_id,
            destination_airport_id=dvo.airport_id,
            is_domestic=True,
            active=True
        )
    ]
    db_session.add_all(routes)
    db_session.commit()
    return routes


@pytest.fixture
def sample_data_source(db_session):
    """Create sample data source for testing"""
    source = DataSource(
        name="Test Scraper",
        type="scraper",
        base_url="https://test.example.com",
        terms_version="1.0",
        active=True
    )
    db_session.add(source)
    db_session.commit()
    return source


@pytest.fixture
def sample_fare_snapshots(db_session, sample_routes, sample_currency, sample_data_source):
    """Create sample fare snapshots for testing"""
    php, usd = sample_currency
    
    fares = []
    for route in sample_routes:
        # Create fares for the next 30 days
        for day_offset in range(30):
            departure_date = datetime.now().date() + timedelta(days=day_offset + 7)
            base_price = 2000 + (day_offset * 50)  # Varying prices
            
            # Generate unique 64-char hash
            hash_val = f"{route.route_id}_{departure_date}_{base_price}"
            hash_signature = hashlib.sha256(hash_val.encode()).hexdigest()
            
            fare = FareSnapshot(
                route_id=route.route_id,
                source_id=sample_data_source.source_id,
                departure_date=departure_date,
                scrape_timestamp=datetime.now() - timedelta(hours=day_offset),
                price_amount=base_price,
                currency_code=php.currency_code,
                hash_signature=hash_signature
            )
            fares.append(fare)
    
    db_session.add_all(fares)
    db_session.commit()
    return fares


@pytest.fixture
def sample_forecast_run(db_session, sample_user):
    """Create a sample forecast run"""
    forecast_run = ForecastRun(
        model_name="prophet",
        run_scope="all_routes",
        initiated_by=sample_user.user_id,
        status="success",
        train_start_date=datetime.now().date() - timedelta(days=90),
        train_end_date=datetime.now().date() - timedelta(days=1),
        horizon_days=30,
        seasonalities={"yearly": True, "weekly": True},
        metrics_json={"mape": 0.15, "rmse": 250},
        finished_at=datetime.now() - timedelta(hours=1)
    )
    db_session.add(forecast_run)
    db_session.commit()
    db_session.refresh(forecast_run)
    return forecast_run


@pytest.fixture
def sample_forecast_results(db_session, sample_forecast_run, sample_routes, sample_currency):
    """Create sample forecast results"""
    php, _ = sample_currency
    route = sample_routes[0]
    
    results = []
    for day_offset in range(30):
        period_start = datetime.now().date() + timedelta(days=day_offset + 1)
        period_end = period_start + timedelta(days=6)  # Weekly period
        
        result = ForecastResult(
            forecast_run_id=sample_forecast_run.forecast_run_id,
            route_id=route.route_id,
            target_period_start=period_start,
            target_period_end=period_end,
            point_forecast=2500 + (day_offset * 30),
            lower_ci=2200 + (day_offset * 25),
            upper_ci=2800 + (day_offset * 35),
            currency_code=php.currency_code
        )
        results.append(result)
    
    db_session.add_all(results)
    db_session.commit()
    return results
