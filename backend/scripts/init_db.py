"""
SmartLipad Backend - Database Initialization Script

This script initializes the database with:
- Required tables
- Default currencies
- Sample Philippine airports
- Default user roles
"""
import sys
from pathlib import Path

# Add project root to path (parent of backend directory)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database import engine, Base, SessionLocal
from backend.models import Currency, Airport, Airline, Role
from backend.core.logging import app_logger


def create_tables():
    """Create all database tables"""
    app_logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    app_logger.info("Database tables created successfully")


def seed_currencies(db):
    """Seed initial currency data"""
    currencies = [
        {"currency_code": "PHP", "name": "Philippine Peso", "symbol": "₱"},
        {"currency_code": "USD", "name": "US Dollar", "symbol": "$"},
    ]
    
    for curr_data in currencies:
        existing = db.query(Currency).filter(
            Currency.currency_code == curr_data["currency_code"]
        ).first()
        
        if not existing:
            currency = Currency(**curr_data)
            db.add(currency)
            app_logger.info(f"Added currency: {curr_data['currency_code']}")
    
    db.commit()


def seed_airports(db):
    """Seed Philippine airports"""
    airports = [
        {
            "iata_code": "MNL",
            "name": "Ninoy Aquino International Airport",
            "city": "Manila",
            "country": "Philippines",
            "latitude": 14.5086,
            "longitude": 121.0194,
            "timezone": "Asia/Manila"
        },
        {
            "iata_code": "CEB",
            "name": "Mactan-Cebu International Airport",
            "city": "Cebu",
            "country": "Philippines",
            "latitude": 10.3075,
            "longitude": 123.9790,
            "timezone": "Asia/Manila"
        },
        {
            "iata_code": "DVO",
            "name": "Francisco Bangoy International Airport",
            "city": "Davao",
            "country": "Philippines",
            "latitude": 7.1255,
            "longitude": 125.6456,
            "timezone": "Asia/Manila"
        },
        {
            "iata_code": "KLO",
            "name": "Kalibo International Airport",
            "city": "Kalibo",
            "country": "Philippines",
            "latitude": 11.6794,
            "longitude": 122.3761,
            "timezone": "Asia/Manila"
        },
        {
            "iata_code": "ILO",
            "name": "Iloilo International Airport",
            "city": "Iloilo",
            "country": "Philippines",
            "latitude": 10.8330,
            "longitude": 122.4933,
            "timezone": "Asia/Manila"
        },
        {
            "iata_code": "CRK",
            "name": "Clark International Airport",
            "city": "Angeles",
            "country": "Philippines",
            "latitude": 15.1859,
            "longitude": 120.5600,
            "timezone": "Asia/Manila"
        },
        {
            "iata_code": "BCD",
            "name": "Bacolod-Silay Airport",
            "city": "Bacolod",
            "country": "Philippines",
            "latitude": 10.7764,
            "longitude": 123.0144,
            "timezone": "Asia/Manila"
        },
        {
            "iata_code": "TAG",
            "name": "Tagbilaran Airport",
            "city": "Tagbilaran",
            "country": "Philippines",
            "latitude": 9.6541,
            "longitude": 123.8531,
            "timezone": "Asia/Manila"
        },
    ]
    
    for airport_data in airports:
        existing = db.query(Airport).filter(
            Airport.iata_code == airport_data["iata_code"]
        ).first()
        
        if not existing:
            airport = Airport(**airport_data)
            db.add(airport)
            app_logger.info(f"Added airport: {airport_data['iata_code']} - {airport_data['name']}")
    
    db.commit()


def seed_airlines(db):
    """Seed Philippine airlines"""
    airlines = [
        {"iata_code": "PR", "name": "Philippine Airlines", "country": "Philippines"},
        {"iata_code": "5J", "name": "Cebu Pacific", "country": "Philippines"},
        {"iata_code": "Z2", "name": "AirAsia Philippines", "country": "Philippines"},
        {"iata_code": "DG", "name": "Cebgo", "country": "Philippines"},
    ]
    
    for airline_data in airlines:
        existing = db.query(Airline).filter(
            Airline.iata_code == airline_data["iata_code"]
        ).first()
        
        if not existing:
            airline = Airline(**airline_data, active=True)
            db.add(airline)
            app_logger.info(f"Added airline: {airline_data['iata_code']} - {airline_data['name']}")
    
    db.commit()


def seed_roles(db):
    """Seed user roles"""
    roles = [
        {"role_name": "admin", "description": "System administrator with full access"},
        {"role_name": "user", "description": "Regular user with basic access"},
        {"role_name": "analyst", "description": "Can run forecasts and view analytics"},
    ]
    
    for role_data in roles:
        existing = db.query(Role).filter(
            Role.role_name == role_data["role_name"]
        ).first()
        
        if not existing:
            role = Role(**role_data)
            db.add(role)
            app_logger.info(f"Added role: {role_data['role_name']}")
    
    db.commit()


def main():
    """Main initialization function"""
    app_logger.info("=" * 60)
    app_logger.info("SmartLipad Database Initialization")
    app_logger.info("=" * 60)
    
    try:
        # Create tables
        create_tables()
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Seed initial data
            app_logger.info("\nSeeding initial data...")
            seed_currencies(db)
            seed_airports(db)
            seed_airlines(db)
            seed_roles(db)
            
            app_logger.info("\n" + "=" * 60)
            app_logger.info("Database initialization completed successfully!")
            app_logger.info("=" * 60)
            
        finally:
            db.close()
    
    except Exception as e:
        app_logger.error(f"Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    main()
