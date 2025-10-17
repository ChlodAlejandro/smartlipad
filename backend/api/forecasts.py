"""
SmartLipad Backend - Forecasting API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import List, Optional
from datetime import date, timedelta

from backend.database import get_db
from backend.schemas import (
    ForecastRequest, ForecastResponse, ForecastResultResponse,
    RouteResponse, AirportResponse, MonthlyForecastSummary
)
from backend.models import Route, Airport, ForecastRun, ForecastResult
from backend.forecasting import FareForecaster
from backend.api.auth import get_current_user
from backend.models import User
from backend.core.logging import app_logger

router = APIRouter()


@router.post("/generate", response_model=ForecastResponse)
async def generate_forecast(
    request: ForecastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate new fare forecast for a route
    
    This endpoint triggers a new forecast run using Prophet model
    """
    # Find airports
    origin = db.query(Airport).filter(
        Airport.iata_code == request.origin_iata.upper()
    ).first()
    
    destination = db.query(Airport).filter(
        Airport.iata_code == request.destination_iata.upper()
    ).first()
    
    if not origin or not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found"
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
            detail=f"No active route from {request.origin_iata} to {request.destination_iata}"
        )
    
    # Initialize forecaster
    forecaster = FareForecaster(db)
    
    try:
        # Run forecast
        horizon_days = request.forecast_months * 30
        forecast_run_id = forecaster.run_forecast_for_route(
            route_id=route.route_id,
            lookback_days=180,
            horizon_days=horizon_days,
            user_id=current_user.user_id
        )
        
        app_logger.info(
            f"Forecast generated: run_id={forecast_run_id}, "
            f"route={request.origin_iata}->{request.destination_iata}, "
            f"user={current_user.email}"
        )
        
        # Fetch results
        return await get_forecast_results(route.route_id, db)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        app_logger.error(f"Forecast generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Forecast generation failed"
        )


@router.get("/route/{route_id}", response_model=ForecastResponse)
async def get_forecast_by_route(
    route_id: int,
    db: Session = Depends(get_db)
):
    """Get latest forecast for a route"""
    return await get_forecast_results(route_id, db)


async def get_forecast_results(route_id: int, db: Session) -> ForecastResponse:
    """Helper function to fetch and format forecast results"""
    
    # Verify route exists
    route = db.query(Route).filter(Route.route_id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found"
        )
    
    # Get latest successful forecast run for this route
    latest_run = db.query(ForecastRun).filter(
        ForecastRun.status == "success"
    ).order_by(desc(ForecastRun.created_at)).first()
    
    if not latest_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast available for this route. Please generate a forecast first."
        )
    
    # Get forecast results for this route
    results = db.query(ForecastResult).filter(
        and_(
            ForecastResult.forecast_run_id == latest_run.forecast_run_id,
            ForecastResult.route_id == route_id
        )
    ).order_by(ForecastResult.target_period_start).all()
    
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast results found"
        )
    
    # Find best and worst months
    best_month = min(results, key=lambda r: r.point_forecast)
    worst_month = max(results, key=lambda r: r.point_forecast)
    
    # Calculate average
    avg_fare = sum(r.point_forecast for r in results) / len(results)
    
    # Prepare route response
    route_response = RouteResponse(
        route_id=route.route_id,
        origin_airport_id=route.origin_airport_id,
        destination_airport_id=route.destination_airport_id,
        is_domestic=route.is_domestic,
        distance_km=route.distance_km,
        active=route.active,
        origin_airport=AirportResponse.model_validate(route.origin_airport),
        destination_airport=AirportResponse.model_validate(route.destination_airport)
    )
    
    return ForecastResponse(
        route=route_response,
        forecasts=[ForecastResultResponse.model_validate(r) for r in results],
        best_month=ForecastResultResponse.model_validate(best_month),
        worst_month=ForecastResultResponse.model_validate(worst_month),
        average_fare=float(avg_fare),
        forecast_run_id=latest_run.forecast_run_id
    )


@router.get("/cheapest-months", response_model=List[MonthlyForecastSummary])
async def get_cheapest_months(
    origin_iata: str = Query(..., max_length=3),
    destination_iata: str = Query(..., max_length=3),
    limit: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db)
):
    """
    Get cheapest months to travel for a route
    
    Returns monthly summaries sorted by price (cheapest first)
    """
    # Find route
    origin = db.query(Airport).filter(Airport.iata_code == origin_iata.upper()).first()
    destination = db.query(Airport).filter(Airport.iata_code == destination_iata.upper()).first()
    
    if not origin or not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found"
        )
    
    route = db.query(Route).filter(
        and_(
            Route.origin_airport_id == origin.airport_id,
            Route.destination_airport_id == destination.airport_id
        )
    ).first()
    
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route not found"
        )
    
    # Get latest forecast results
    latest_run = db.query(ForecastRun).filter(
        ForecastRun.status == "success"
    ).order_by(desc(ForecastRun.created_at)).first()
    
    if not latest_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast available"
        )
    
    results = db.query(ForecastResult).filter(
        and_(
            ForecastResult.forecast_run_id == latest_run.forecast_run_id,
            ForecastResult.route_id == route.route_id
        )
    ).order_by(ForecastResult.point_forecast.asc()).limit(limit).all()
    
    # Find peak price for percentage calculation
    all_results = db.query(ForecastResult).filter(
        and_(
            ForecastResult.forecast_run_id == latest_run.forecast_run_id,
            ForecastResult.route_id == route.route_id
        )
    ).all()
    
    peak_price = max(r.point_forecast for r in all_results)
    
    # Format results
    summaries = []
    for result in results:
        percent_vs_peak = ((peak_price - result.point_forecast) / peak_price) * 100
        
        summaries.append(MonthlyForecastSummary(
            month=result.target_period_start.strftime("%Y-%m"),
            average_fare=float(result.point_forecast),
            min_fare=float(result.lower_ci) if result.lower_ci else float(result.point_forecast),
            max_fare=float(result.upper_ci) if result.upper_ci else float(result.point_forecast),
            currency_code=result.currency_code,
            percent_vs_peak=round(percent_vs_peak, 2)
        ))
    
    return summaries
