"""
SmartLipad Backend - Flight Search API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import date, datetime, timedelta
from typing import List, Optional

from backend.database import get_db
from backend.schemas import (
    FareSearchRequest, FareSearchResponse, FareSnapshotResponse,
    RouteResponse, AirportResponse
)
from backend.models import FareSnapshot, Route, Airport, Airline
from backend.core.logging import app_logger

router = APIRouter()


@router.post("/search", response_model=FareSearchResponse)
async def search_flights(
    search_request: FareSearchRequest,
    db: Session = Depends(get_db)
):
    """Search for flight fares based on route and date"""
    
    # Find origin and destination airports
    origin = db.query(Airport).filter(Airport.iata_code == search_request.origin_iata.upper()).first()
    destination = db.query(Airport).filter(Airport.iata_code == search_request.destination_iata.upper()).first()
    
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Origin airport '{search_request.origin_iata}' not found"
        )
    
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination airport '{search_request.destination_iata}' not found"
        )
    
    # Find route
    route = db.query(Route).filter(
        and_(
            Route.origin_airport_id == origin.airport_id,
            Route.destination_airport_id == destination.airport_id,
            Route.active == True
        )
    ).first()
    
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active route found from {search_request.origin_iata} to {search_request.destination_iata}"
        )
    
    # Build query for fare snapshots
    query = db.query(FareSnapshot).filter(
        and_(
            FareSnapshot.route_id == route.route_id,
            FareSnapshot.is_valid == True
        )
    )
    
    # Filter by departure date if specified
    if search_request.departure_date:
        query = query.filter(FareSnapshot.departure_date == search_request.departure_date)
    else:
        # Default to fares for next 30 days
        today = date.today()
        query = query.filter(
            and_(
                FareSnapshot.departure_date >= today,
                FareSnapshot.departure_date <= today + timedelta(days=30)
            )
        )
    
    # Order by price (ascending) and limit results
    fares = query.order_by(FareSnapshot.price_amount.asc()).limit(search_request.limit).all()
    
    # Get total count
    total_count = query.count()
    
    app_logger.info(f"Flight search: {search_request.origin_iata} -> {search_request.destination_iata}, found {total_count} fares")
    
    # Prepare route response with airport details
    route_response = RouteResponse(
        route_id=route.route_id,
        origin_airport_id=route.origin_airport_id,
        destination_airport_id=route.destination_airport_id,
        is_domestic=route.is_domestic,
        distance_km=route.distance_km,
        active=route.active,
        origin_airport=AirportResponse.model_validate(origin),
        destination_airport=AirportResponse.model_validate(destination)
    )
    
    return FareSearchResponse(
        route=route_response,
        fares=[FareSnapshotResponse.model_validate(fare) for fare in fares],
        total_count=total_count
    )


@router.get("/airports", response_model=List[AirportResponse])
async def get_airports(
    country: Optional[str] = Query(None, description="Filter by country"),
    city: Optional[str] = Query(None, description="Filter by city"),
    db: Session = Depends(get_db)
):
    """Get list of airports"""
    query = db.query(Airport)
    
    if country:
        query = query.filter(Airport.country.ilike(f"%{country}%"))
    
    if city:
        query = query.filter(Airport.city.ilike(f"%{city}%"))
    
    airports = query.order_by(Airport.city, Airport.name).all()
    
    return [AirportResponse.model_validate(airport) for airport in airports]


@router.get("/routes/{route_id}/latest-fares", response_model=List[FareSnapshotResponse])
async def get_latest_fares_for_route(
    route_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get latest fares for a specific route"""
    
    # Verify route exists
    route = db.query(Route).filter(Route.route_id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found"
        )
    
    # Get latest fares
    fares = db.query(FareSnapshot).filter(
        and_(
            FareSnapshot.route_id == route_id,
            FareSnapshot.is_valid == True
        )
    ).order_by(
        FareSnapshot.scrape_timestamp.desc()
    ).limit(limit).all()
    
    return [FareSnapshotResponse.model_validate(fare) for fare in fares]


@router.get("/cheapest", response_model=List[FareSnapshotResponse])
async def get_cheapest_fares(
    days_ahead: int = Query(30, ge=1, le=365, description="Number of days to look ahead"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get cheapest fares across all routes for upcoming dates"""
    
    today = date.today()
    end_date = today + timedelta(days=days_ahead)
    
    # Subquery to get minimum price per route and departure date
    subquery = db.query(
        FareSnapshot.route_id,
        FareSnapshot.departure_date,
        func.min(FareSnapshot.price_amount).label('min_price')
    ).filter(
        and_(
            FareSnapshot.is_valid == True,
            FareSnapshot.departure_date >= today,
            FareSnapshot.departure_date <= end_date
        )
    ).group_by(
        FareSnapshot.route_id,
        FareSnapshot.departure_date
    ).subquery()
    
    # Get actual fare records with minimum prices
    cheapest_fares = db.query(FareSnapshot).join(
        subquery,
        and_(
            FareSnapshot.route_id == subquery.c.route_id,
            FareSnapshot.departure_date == subquery.c.departure_date,
            FareSnapshot.price_amount == subquery.c.min_price
        )
    ).order_by(FareSnapshot.price_amount.asc()).limit(limit).all()
    
    return [FareSnapshotResponse.model_validate(fare) for fare in cheapest_fares]
