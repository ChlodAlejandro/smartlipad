from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import date, datetime, timedelta
from typing import List, Optional, Any, Dict, Tuple
from backend.database import get_db
from backend.schemas import (
    FareSearchRequest, FareSearchResponse, FareSnapshotResponse,
    RouteResponse, AirportResponse
)
from backend.models import FareSnapshot, Route, Airport, Airline, ForecastRun, ForecastResult, Currency
from backend.core.logging import app_logger
from backend.core.config import get_settings
import logging
import calendar
import time
from collections import defaultdict
from statistics import mean
from dateutil.relativedelta import relativedelta
import threading

logging.getLogger("uvicorn.error").info(f"Loading flights router from: {__file__}")

router = APIRouter()
settings = get_settings()
_latest_tokens: Dict[Tuple[str, str], str] = {}
_latest_lock = threading.Lock()

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Origin airport '{search_request.origin_iata}' not found")
    if not destination:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Destination airport '{search_request.destination_iata}' not found")
    route = db.query(Route).filter(
        and_(
            Route.origin_airport_id == origin.airport_id,
            Route.destination_airport_id == destination.airport_id,
            Route.active == True
        )
    ).first()
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active route found from {search_request.origin_iata} to {search_request.destination_iata}")
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
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Route {route_id} not found")
    fares = db.query(FareSnapshot).filter(
        and_(
            FareSnapshot.route_id == route_id,
            FareSnapshot.is_valid == True
        )
    ).order_by(FareSnapshot.scrape_timestamp.desc()).limit(limit).all()
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

def _amadeus_day_min(cli, origin, destination, day_iso, currency="PHP"):
    try:
        r = cli.shopping.flight_offers_search.get(
            originLocationCode=origin,
            destinationLocationCode=destination,
            departureDate=day_iso,
            adults=1,
            currencyCode=currency
        )
        data = r.data or []
    except Exception as e:
        app_logger.error(f"amadeus day_min error {origin}-{destination} {day_iso}: {e}")
        return None
    prices = []
    for o in data:
        p = (o.get("price") or {}).get("grandTotal") or (o.get("price") or {}).get("total")
        if p:
            try:
                prices.append(float(p))
            except:
                pass
    return min(prices) if prices else None

def _db_alpha_backfill(db: Session, origin_u: str, dest_u: str, months: int, monthly: List[Dict]) -> Tuple[List[Dict], str]:
    try:
        o = db.query(Airport).filter(Airport.iata_code == origin_u).first()
        d = db.query(Airport).filter(Airport.iata_code == dest_u).first()
        if not o or not d:
            return monthly, "none"
        route = db.query(Route).filter(
            and_(Route.origin_airport_id == o.airport_id, Route.destination_airport_id == d.airport_id, Route.active == True)
        ).first()
        if not route:
            return monthly, "none"
        today = date.today()
        history_start = today - timedelta(days=540)
        rows = db.query(FareSnapshot).filter(
            and_(
                FareSnapshot.route_id == route.route_id,
                FareSnapshot.is_valid == True,
                FareSnapshot.price_amount.isnot(None),
                FareSnapshot.departure_date.isnot(None),
                FareSnapshot.departure_date >= history_start,
                FareSnapshot.departure_date < today + timedelta(days=365)
            )
        ).all()
        daily_min = {}
        for r in rows:
            dd = r.departure_date
            p = float(r.price_amount)
            if dd not in daily_min or p < daily_min[dd]:
                daily_min[dd] = p
        hist_month = defaultdict(list)
        for dd, p in daily_min.items():
            key = f"{dd.year:04d}-{dd.month:02d}"
            hist_month[key].append(p)
        hist_month_avg = {k: mean(v) for k, v in hist_month.items() if v}
        overall = round(mean(hist_month_avg.values())) if hist_month_avg else None
        alpha = 0.7
        if not monthly:
            first_month = date(today.year, today.month, 1)
            cur = first_month
            for _ in range(months):
                key = f"{cur.year:04d}-{cur.month:02d}"
                monthly.append({"month": key, "avg_fare": None})
                cur = cur + relativedelta(months=1)
        for i, item in enumerate(monthly):
            if item["avg_fare"] is None:
                y_m = item["month"].split("-")
                cur_dt = date(int(y_m[0]), int(y_m[1]), 1)
                ly_dt = cur_dt - relativedelta(years=1)
                ly_key = f"{ly_dt.year:04d}-{ly_dt.month:02d}"
                ly = hist_month_avg.get(ly_key)
                if ly is not None or overall is not None:
                    base = ly if ly is not None else overall
                    pred = round(alpha * (ly if ly is not None else base) + (1 - alpha) * (overall if overall is not None else base))
                    monthly[i]["avg_fare"] = int(pred)
        return monthly, "db"
    except Exception as e:
        app_logger.error(f"[predictions] backfill error: {e}")
        return monthly, "none"

def _resolve_route(db: Session, origin_u: str, dest_u: str) -> Optional[Route]:
    o = db.query(Airport).filter(Airport.iata_code == origin_u).first()
    d = db.query(Airport).filter(Airport.iata_code == dest_u).first()
    if not o or not d:
        return None
    return db.query(Route).filter(
        and_(Route.origin_airport_id == o.airport_id, Route.destination_airport_id == d.airport_id, Route.active == True)
    ).first()

def _persist_simple_run(db: Session, origin_u: str, dest_u: str, monthly: List[Dict], label: str) -> Optional[int]:
    route = _resolve_route(db, origin_u, dest_u)
    if not route:
        return None
    valued = [x for x in monthly if isinstance(x.get("avg_fare"), (int, float)) and x["avg_fare"] is not None]
    if not valued:
        return None
    run = ForecastRun(
        model_name=label,
        run_scope="route",
        status="success",
        train_start_date=date.today() - timedelta(days=365),
        train_end_date=date.today(),
        horizon_days=30 * len(valued),
        seasonalities={"mode": "none"},
        metrics_json={}
    )
    db.add(run)
    db.flush()
    php = db.query(Currency).filter(Currency.currency_code == "PHP").first()
    currency = php.currency_code if php else "PHP"
    for item in valued:
        y, m = item["month"].split("-")
        start = date(int(y), int(m), 1)
        end = (start.replace(day=28) + timedelta(days=8)).replace(day=1) - timedelta(days=1)
        db.add(ForecastResult(
            forecast_run_id=run.forecast_run_id,
            route_id=route.route_id,
            target_period_start=start,
            target_period_end=end,
            point_forecast=float(item["avg_fare"]),
            lower_ci=float(item["avg_fare"]) * 0.9,
            upper_ci=float(item["avg_fare"]) * 1.1,
            currency_code=currency,
            model_version="simple-1"
        ))
    db.commit()
    return run.forecast_run_id

@router.get("/predictions")
async def get_predictions(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    months: int = Query(None, ge=1, le=24),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    t0 = time.perf_counter()
    origin_u = origin.upper()
    dest_u = destination.upper()
    route_key = (origin_u, dest_u)
    if token:
        with _latest_lock:
            _latest_tokens[route_key] = token
    def is_superseded():
        if not token:
            return False
        with _latest_lock:
            return _latest_tokens.get(route_key) != token
    horizon = months or getattr(settings, "PREDICTION_MONTHS_DEFAULT", 12)
    horizon = min(horizon, getattr(settings, "PREDICTION_MONTHS_MAX", 24))
    monthly: List[Dict] = []
    provenance = []
    if is_superseded():
        return {
            "origin": origin_u,
            "destination": dest_u,
            "monthly_forecast": [],
            "best_time": None,
            "most_expensive": None,
            "avg_fare": 0,
            "source": "none",
            "superseded": True
        }
    if getattr(settings, "PROPHET_ENABLED", False):
        try:
            from backend.forecasting.prophet_service import get_or_train_monthly_forecast
            mlist, src = get_or_train_monthly_forecast(db, origin_u, dest_u, horizon)
            if is_superseded():
                return {
                    "origin": origin_u,
                    "destination": dest_u,
                    "monthly_forecast": [],
                    "best_time": None,
                    "most_expensive": None,
                    "avg_fare": 0,
                    "source": "prophet",
                    "superseded": True
                }
            monthly = mlist or []
            if src != "none":
                provenance.append(src)
        except Exception as e:
            app_logger.error(f"[predictions] prophet path error: {e}")
    missing = not monthly or any(x.get("avg_fare") in (None, 0) for x in monthly)
    if missing and settings.DATA_PROVIDER == "amadeus":
        cli = _amadeus_client()
        if cli:
            today = date.today()
            y, m = today.year, today.month
            sample_days = (5, 15, 25)
            if not monthly:
                for i in range(horizon):
                    monthly.append({"month": f"{y:04d}-{m:02d}", "avg_fare": None})
                    if m == 12:
                        y += 1
                        m = 1
                    else:
                        m += 1
                y, m = today.year, today.month
            for i in range(horizon):
                if is_superseded():
                    return {
                        "origin": origin_u,
                        "destination": dest_u,
                        "monthly_forecast": [],
                        "best_time": None,
                        "most_expensive": None,
                        "avg_fare": 0,
                        "source": "+".join(provenance) if provenance else "none",
                        "superseded": True
                    }
                if monthly[i]["avg_fare"] is None:
                    prices = []
                    last_day = calendar.monthrange(y, m)[1]
                    for d in sample_days:
                        if d <= last_day:
                            day_iso = date(y, m, d).isoformat()
                            app_logger.info(f"[predictions] amadeus {origin_u}-{dest_u} month={y}-{m:02d} day={day_iso} ({i+1}/{horizon})")
                            p = _amadeus_day_min(cli, origin_u, dest_u, day_iso, "PHP")
                            if p is not None:
                                prices.append(p)
                    avg = int(round(mean(prices))) if prices else None
                    monthly[i]["avg_fare"] = avg
                if m == 12:
                    y += 1
                    m = 1
                else:
                    m += 1
            provenance.append("amadeus")
    if not monthly or any(x.get("avg_fare") is None for x in monthly):
        monthly, src = _db_alpha_backfill(db, origin_u, dest_u, horizon, monthly)
        if src != "none":
            provenance.append(src)
    valued = [x for x in monthly if isinstance(x.get("avg_fare"), (int, float)) and x["avg_fare"] is not None]
    if valued:
        if not any(p.startswith("prophet") for p in provenance):
            try:
                _persist_simple_run(db, origin_u, dest_u, valued, "+".join(provenance) if provenance else "simple")
            except Exception as e:
                app_logger.error(f"[predictions] persist simple run error: {e}")
        best = min(valued, key=lambda x: x["avg_fare"])
        worst = max(valued, key=lambda x: x["avg_fare"])
        overall = int(round(sum(x["avg_fare"] for x in valued) / len(valued)))
        app_logger.info(f"[predictions] done source={'+'.join(provenance) if provenance else 'none'} months={len(monthly)} with_vals={len(valued)} elapsed={time.perf_counter()-t0:.2f}s")
        return {
            "origin": origin_u,
            "destination": dest_u,
            "monthly_forecast": monthly,
            "best_time": {"month": best["month"], "price": best["avg_fare"]},
            "most_expensive": {"month": worst["month"], "price": worst["avg_fare"]},
            "avg_fare": overall,
            "source": "+".join(provenance) if provenance else "none"
        }
    app_logger.info(f"[predictions] no-data source={'+'.join(provenance) if provenance else 'none'} elapsed={time.perf_counter()-t0:.2f}s")
    return {
        "origin": origin_u,
        "destination": dest_u,
        "monthly_forecast": monthly,
        "best_time": None,
        "most_expensive": None,
        "avg_fare": 0,
        "source": "+".join(provenance) if provenance else "none"
    }
