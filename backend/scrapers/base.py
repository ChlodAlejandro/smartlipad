"""
SmartLipad Backend - Web Scraping Base Module
"""
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import List, Dict, Optional
import hashlib
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from backend.models import DataSource, ScrapeJob, ScrapeJobLog, FareSnapshot
from backend.core.config import get_settings
from backend.core.logging import app_logger

settings = get_settings()


class BaseScraper(ABC):
    """
    Abstract base class for airline fare scrapers
    
    All scrapers should inherit from this class and implement
    the abstract methods.
    """
    
    def __init__(self, db: Session, source_name: str):
        """
        Initialize scraper
        
        Args:
            db: Database session
            source_name: Name of the data source
        """
        self.db = db
        self.source_name = source_name
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': settings.SCRAPER_USER_AGENT
        })
        
        # Get or create data source
        self.data_source = self._get_or_create_source()
        self.current_job: Optional[ScrapeJob] = None
    
    def _get_or_create_source(self) -> DataSource:
        """Get existing data source or create new one"""
        source = self.db.query(DataSource).filter(
            DataSource.name == self.source_name
        ).first()
        
        if not source:
            source = DataSource(
                name=self.source_name,
                type="scraper",
                active=True
            )
            self.db.add(source)
            self.db.commit()
            self.db.refresh(source)
            app_logger.info(f"Created new data source: {self.source_name}")
        
        return source
    
    def create_scrape_job(self) -> ScrapeJob:
        """Create a new scrape job"""
        job = ScrapeJob(
            source_id=self.data_source.source_id,
            status="queued",
            scheduled_at=datetime.utcnow()
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        self.current_job = job
        app_logger.info(f"Created scrape job {job.job_id} for {self.source_name}")
        
        return job
    
    def start_job(self):
        """Mark job as running"""
        if self.current_job:
            self.current_job.status = "running"
            self.current_job.started_at = datetime.utcnow()
            self.db.commit()
    
    def finish_job(self, status: str = "success", error_message: str = None):
        """Mark job as finished"""
        if self.current_job:
            self.current_job.status = status
            self.current_job.finished_at = datetime.utcnow()
            if error_message:
                self.current_job.error_message = error_message
            self.db.commit()
            
            app_logger.info(
                f"Job {self.current_job.job_id} finished with status: {status}, "
                f"captured: {self.current_job.total_captured}, "
                f"errors: {self.current_job.total_errors}"
            )
    
    def log_attempt(
        self,
        route_id: Optional[int],
        url: str,
        success: bool,
        http_status: Optional[int] = None,
        message: str = None
    ):
        """Log scraping attempt"""
        if self.current_job:
            log = ScrapeJobLog(
                job_id=self.current_job.job_id,
                route_id=route_id,
                url=url,
                http_status=http_status,
                success=success,
                message=message
            )
            self.db.add(log)
            
            # Update job counters
            self.current_job.total_attempted += 1
            if success:
                self.current_job.total_captured += 1
            else:
                self.current_job.total_errors += 1
            
            self.db.commit()
    
    def generate_fare_hash(self, fare_data: Dict) -> str:
        """Generate unique hash for fare snapshot"""
        hash_string = f"{fare_data['route_id']}_{fare_data['departure_date']}_" \
                     f"{fare_data['price_amount']}_{fare_data['scrape_timestamp']}_" \
                     f"{fare_data.get('airline_id', 'NA')}"
        
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def save_fare_snapshot(self, fare_data: Dict) -> Optional[FareSnapshot]:
        """
        Save fare snapshot to database
        
        Args:
            fare_data: Dictionary with fare information
            
        Returns:
            FareSnapshot instance if saved, None if duplicate
        """
        # Generate hash
        fare_hash = self.generate_fare_hash(fare_data)
        
        # Check for duplicate
        existing = self.db.query(FareSnapshot).filter(
            FareSnapshot.hash_signature == fare_hash
        ).first()
        
        if existing:
            app_logger.debug(f"Duplicate fare skipped: {fare_hash}")
            return None
        
        # Create fare snapshot
        snapshot = FareSnapshot(
            route_id=fare_data['route_id'],
            airline_id=fare_data.get('airline_id'),
            source_id=self.data_source.source_id,
            departure_date=fare_data['departure_date'],
            scrape_timestamp=fare_data['scrape_timestamp'],
            price_amount=fare_data['price_amount'],
            currency_code=fare_data.get('currency_code', 'PHP'),
            cabin_class=fare_data.get('cabin_class'),
            fare_type=fare_data.get('fare_type'),
            seats_remaining=fare_data.get('seats_remaining'),
            hash_signature=fare_hash,
            is_valid=True
        )
        
        self.db.add(snapshot)
        self.db.commit()
        
        return snapshot
    
    @abstractmethod
    def scrape_route(self, route_id: int, origin_iata: str, destination_iata: str) -> List[Dict]:
        """
        Scrape fares for a specific route
        
        Args:
            route_id: Database route ID
            origin_iata: Origin airport IATA code
            destination_iata: Destination airport IATA code
            
        Returns:
            List of fare dictionaries
        """
        pass
    
    @abstractmethod
    def scrape_all_routes(self) -> int:
        """
        Scrape all active routes
        
        Returns:
            Number of fares collected
        """
        pass


class SkyscannerScraper(BaseScraper):
    """
    Scraper for Skyscanner API/website
    
    Note: This is a template. Actual implementation would need
    proper API credentials and error handling.
    """
    
    def __init__(self, db: Session):
        super().__init__(db, "Skyscanner")
    
    def scrape_route(self, route_id: int, origin_iata: str, destination_iata: str) -> List[Dict]:
        """Scrape fares from Skyscanner"""
        fares = []
        
        # This is a placeholder - actual implementation would use Skyscanner API
        # or scrape their website with proper authentication
        
        app_logger.info(f"Scraping {origin_iata} -> {destination_iata} from Skyscanner")
        
        # Example URL (not functional without proper setup)
        url = f"https://www.skyscanner.com/transport/flights/{origin_iata}/{destination_iata}/"
        
        try:
            response = self.session.get(url, timeout=settings.SCRAPER_TIMEOUT)
            
            if response.status_code == 200:
                # Parse response (placeholder)
                # In real implementation, parse HTML or JSON response
                
                self.log_attempt(route_id, url, True, response.status_code)
            else:
                self.log_attempt(
                    route_id, url, False, response.status_code,
                    f"HTTP {response.status_code}"
                )
        
        except Exception as e:
            app_logger.error(f"Scraping error for {origin_iata}->{destination_iata}: {e}")
            self.log_attempt(route_id, url, False, None, str(e))
        
        return fares
    
    def scrape_all_routes(self) -> int:
        """Scrape all active routes"""
        from backend.models import Route
        
        self.create_scrape_job()
        self.start_job()
        
        total_fares = 0
        
        try:
            # Get all active domestic routes
            routes = self.db.query(Route).filter(
                Route.active == True,
                Route.is_domestic == True
            ).all()
            
            for route in routes:
                fares = self.scrape_route(
                    route.route_id,
                    route.origin_airport.iata_code,
                    route.destination_airport.iata_code
                )
                
                for fare_data in fares:
                    if self.save_fare_snapshot(fare_data):
                        total_fares += 1
            
            self.finish_job("success")
            
        except Exception as e:
            app_logger.error(f"Scrape job failed: {e}")
            self.finish_job("failed", str(e))
        
        return total_fares
