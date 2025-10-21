from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import date, datetime, timedelta
from typing import List, Optional, Any, Dict
from backend.database import get_db
from backend.schemas import (
    FareSearchRequest, FareSearchResponse, FareSnapshotResponse,
    RouteResponse, AirportResponse
)
from backend.models import FareSnapshot, Route, Airport, Airline
from backend.core.logging import app_logger
from backend.core.config import get_settings

router = APIRouter()
settings = get_settings()

def _amadeus_client():
    try:
        from amadeus import Client
    except Exception:
        return None
    api_key = settings.AMADEUS_API_KEY
    api_secret = settings.AMADEUS_API_SECRET
    env = settings.AMADEUS_ENVIRONMENT or "test"
    if not api_key or not api_secret:
        return None
    return Client(client_id=api_key, client_secret=api_secret, hostname="test" if env == "test" else "production")

def _parse_amadeus_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    price = offer.get("price", {}).get("grandTotal")
    price_num = float(price) if price is not None else None
    itin = (offer.get("itineraries") or [{}])[0]
    segs = itin.get("segments") or []
    dep_iso = segs[0]["departure"]["at"] if segs else None
    arr_iso = segs[-1]["arrival"]["at"] if segs else None
    dep_time = dep_iso[11:16] if dep_iso else None
    arr_time = arr_iso[11:16] if arr_iso else None
    duration = itin.get("duration", "").replace("PT", "").lower()
    stops = max(len(segs) - 1, 0) if segs else 0
    carrier = None
    if segs:
        carrier = segs[0].get("carrierCode")
    validating = offer.get("validatingAirlineCodes", [])
    airline_code = carrier or (validating[0] if validating else None)
    return {
        "airline_code": airline_code,
        "departure_time": dep_time,
        "arrival_time": arr_time,
        "duration": duration,
        "stops": stops,
        "price": price_num,
        "currency": offer.get("price", {}).get("currency")
    }

@router.get("/flight-offers")
async def flight_offers(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date: str = Query(...),
    adults: int = Query(1, ge=1, le=9),
    currency: str = Query("PHP", min_length=3, max_length=3),
):
    cli = _amadeus_client() if settings.DATA_PROVIDER == "amadeus" else None

    if cli is None:
        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "date": date,
            "currency": currency.upper(),
            "offers": []
        }

    try:
        res = cli.shopping.flight_offers_search.get(
            originLocationCode=origin.upper(),
            destinationLocationCode=destination.upper(),
            departureDate=date,
            adults=adults,
            currencyCode=currency.upper()
        )
        data = res.data or []
        offers = [_parse_amadeus_offer(o) for o in data]
        offers = [o for o in offers if o.get("price") is not None]
        offers.sort(key=lambda x: x["price"])
        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "date": date,
            "currency": currency.upper(),
            "total": len(offers),
            "offers": offers
        }

    except Exception as e:
        app_logger.error(f"Amadeus search failed: {e}")
        raise HTTPException(status_code=502, detail=f"Upstream provider error: {str(e)}")


@router.post("/search", response_model=FareSearchResponse)
async def search_flights(
    search_request: FareSearchRequest,
    db: Session = Depends(get_db)
):
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
    query = db.query(FareSnapshot).filter(
        and_(
            FareSnapshot.route_id == route.route_id,
            FareSnapshot.is_valid == True
        )
    )
    if search_request.departure_date:
        query = query.filter(FareSnapshot.departure_date == search_request.departure_date)
    else:
        today = date.today()
        query = query.filter(
            and_(
                FareSnapshot.departure_date >= today,
                FareSnapshot.departure_date <= today + timedelta(days=30)
            )
        )
    fares = query.order_by(FareSnapshot.price_amount.asc()).limit(search_request.limit).all()
    total_count = query.count()
    app_logger.info(f"Flight search: {search_request.origin_iata} -> {search_request.destination_iata}, found {total_count} fares")
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
    route = db.query(Route).filter(Route.route_id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found"
        )
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
    days_ahead: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    today = date.today()
    end_date = today + timedelta(days=days_ahead)
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
    cheapest_fares = db.query(FareSnapshot).join(
        subquery,
        and_(
            FareSnapshot.route_id == subquery.c.route_id,
            FareSnapshot.departure_date == subquery.c.departure_date,
            FareSnapshot.price_amount == subquery.c.min_price
        )
    ).order_by(FareSnapshot.price_amount.asc()).limit(limit).all()
    return [FareSnapshotResponse.model_validate(fare) for fare in cheapest_fares]
