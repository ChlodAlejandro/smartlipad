from datetime import date, datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from prophet import Prophet
from backend.models import FareSnapshot, Route, Airport, ForecastRun, ForecastResult, Currency
from backend.core.config import get_settings

settings = get_settings()

def _resolve_route(db: Session, origin_iata: str, dest_iata: str) -> Optional[Route]:
    o = db.query(Airport).filter(Airport.iata_code == origin_iata).first()
    d = db.query(Airport).filter(Airport.iata_code == dest_iata).first()
    if not o or not d:
        return None
    return db.query(Route).filter(
        and_(Route.origin_airport_id == o.airport_id, Route.destination_airport_id == d.airport_id, Route.active == True)
    ).first()

def _load_training_df(db: Session, route_id: int) -> pd.DataFrame:
    today = date.today()
    start = today - timedelta(days=730)
    rows = db.query(
        FareSnapshot.departure_date.label("ds"),
        func.min(FareSnapshot.price_amount).label("y")
    ).filter(
        and_(
            FareSnapshot.route_id == route_id,
            FareSnapshot.is_valid == True,
            FareSnapshot.departure_date >= start,
            FareSnapshot.departure_date <= today
        )
    ).group_by(FareSnapshot.departure_date).order_by(FareSnapshot.departure_date.asc()).all()
    if not rows:
        return pd.DataFrame(columns=["ds", "y"])
    df = pd.DataFrame(rows, columns=["ds", "y"])
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"], errors="coerce").astype(float)
    df = df.dropna()
    return df

def _fit_prophet(df: pd.DataFrame) -> Optional[Prophet]:
    if len(df) < 30:
        return None
    m = Prophet(
        seasonality_mode=settings.PROPHET_SEASONALITY_MODE,
        changepoint_prior_scale=settings.PROPHET_CHANGEPOINT_PRIOR_SCALE,
        weekly_seasonality=True,
        yearly_seasonality=True,
        daily_seasonality=False,
    )
    m.fit(df)
    return m

def _forecast_monthly(m: Prophet, months: int) -> pd.DataFrame:
    future = m.make_future_dataframe(periods=max(30 * months, 30), freq="D", include_history=False)
    fc = m.predict(future)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    fc["month"] = fc["ds"].dt.to_period("M").dt.to_timestamp()
    g = fc.groupby("month").agg(yhat=("yhat", "mean"), yhat_lower=("yhat_lower", "mean"), yhat_upper=("yhat_upper", "mean")).reset_index()
    g = g.sort_values("month").head(months)
    return g

def _persist_run_and_results(db: Session, route: Route, monthly_df: pd.DataFrame) -> int:
    run = ForecastRun(
        model_name="prophet",
        run_scope="route",
        status="success",
        train_start_date=(monthly_df["month"].min().date() if not monthly_df.empty else date.today()),
        train_end_date=date.today(),
        horizon_days=30 * len(monthly_df),
        seasonalities={"mode": settings.PROPHET_SEASONALITY_MODE},
        metrics_json={}
    )
    db.add(run)
    db.flush()
    php = db.query(Currency).filter(Currency.currency_code == "PHP").first()
    currency = php.currency_code if php else "PHP"
    for _, r in monthly_df.iterrows():
        start = r["month"].date()
        end = (start.replace(day=28) + timedelta(days=8)).replace(day=1) - timedelta(days=1)
        db.add(ForecastResult(
            forecast_run_id=run.forecast_run_id,
            route_id=route.route_id,
            target_period_start=start,
            target_period_end=end,
            point_forecast=float(r["yhat"]),
            lower_ci=float(r["yhat_lower"]),
            upper_ci=float(r["yhat_upper"]),
            currency_code=currency,
            model_version="1"
        ))
    db.commit()
    return run.forecast_run_id

def _read_cached_months(db: Session, route_id: int, months: int) -> List[Dict]:
    today = date.today().replace(day=1)
    end_month = (today.replace(day=28) + timedelta(days=8)).replace(day=1)
    rows = db.query(ForecastResult).filter(
        and_(
            ForecastResult.route_id == route_id,
            ForecastResult.target_period_start >= today,
        )
    ).order_by(ForecastResult.target_period_start.asc()).all()
    if not rows:
        return []
    seq = []
    seen = set()
    for r in rows:
        key = f"{r.target_period_start.year:04d}-{r.target_period_start.month:02d}"
        if key in seen:
            continue
        seq.append({"month": key, "avg_fare": int(round(float(r.point_forecast)))})
        seen.add(key)
        if len(seq) >= months:
            break
    return seq

def get_or_train_monthly_forecast(db: Session, origin_iata: str, dest_iata: str, months: int) -> Tuple[List[Dict], str]:
    route = _resolve_route(db, origin_iata, dest_iata)
    if not route:
        return [], "none"
    cached = _read_cached_months(db, route.route_id, months)
    if len(cached) >= months:
        return cached, "prophet-cache"
    df = _load_training_df(db, route.route_id)
    model = _fit_prophet(df)
    if not model:
        return [], "none"
    monthly_df = _forecast_monthly(model, months)
    run_id = _persist_run_and_results(db, route, monthly_df)
    fresh = _read_cached_months(db, route.route_id, months)
    return fresh, "prophet"
