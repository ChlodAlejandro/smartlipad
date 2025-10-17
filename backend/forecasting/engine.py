"""
SmartLipad Backend - Forecasting Engine using Facebook Prophet
"""
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from prophet import Prophet
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.models import (
    FareSnapshot, Route, ForecastRun, ForecastResult, 
    ModelParameter, MonthlyLowestFare
)
from backend.core.config import get_settings
from backend.core.logging import app_logger

settings = get_settings()


class FareForecaster:
    """
    Fare forecasting engine using Facebook Prophet
    
    This class handles:
    - Data preparation and cleaning
    - Prophet model training
    - Forecast generation
    - Results storage
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = settings
    
    def prepare_training_data(
        self,
        route_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Prepare historical fare data for training
        
        Args:
            route_id: Route to prepare data for
            start_date: Start of training period (optional)
            end_date: End of training period (optional)
            
        Returns:
            DataFrame with 'ds' (date) and 'y' (price) columns for Prophet
        """
        # Build query
        query = self.db.query(FareSnapshot).filter(
            and_(
                FareSnapshot.route_id == route_id,
                FareSnapshot.is_valid == True
            )
        )
        
        if start_date:
            query = query.filter(FareSnapshot.departure_date >= start_date)
        
        if end_date:
            query = query.filter(FareSnapshot.departure_date <= end_date)
        
        # Fetch data
        snapshots = query.all()
        
        if not snapshots:
            app_logger.warning(f"No training data found for route {route_id}")
            return pd.DataFrame(columns=['ds', 'y'])
        
        # Convert to DataFrame
        data = pd.DataFrame([
            {
                'ds': snapshot.departure_date,
                'y': float(snapshot.price_amount),
                'scrape_timestamp': snapshot.scrape_timestamp
            }
            for snapshot in snapshots
        ])
        
        # Aggregate by date (take minimum price per day)
        data = data.groupby('ds').agg({'y': 'min'}).reset_index()
        
        # Sort by date
        data = data.sort_values('ds')
        
        app_logger.info(f"Prepared {len(data)} data points for route {route_id}")
        
        return data
    
    def train_model(
        self,
        training_data: pd.DataFrame,
        seasonality_mode: str = None,
        changepoint_prior_scale: float = None
    ) -> Prophet:
        """
        Train Prophet model on historical data
        
        Args:
            training_data: DataFrame with 'ds' and 'y' columns
            seasonality_mode: 'additive' or 'multiplicative'
            changepoint_prior_scale: Flexibility of trend changes
            
        Returns:
            Trained Prophet model
        """
        if len(training_data) < 2:
            raise ValueError("Insufficient training data (need at least 2 points)")
        
        # Use settings defaults if not specified
        seasonality_mode = seasonality_mode or self.settings.PROPHET_SEASONALITY_MODE
        changepoint_prior_scale = changepoint_prior_scale or self.settings.PROPHET_CHANGEPOINT_PRIOR_SCALE
        
        # Initialize Prophet model
        model = Prophet(
            seasonality_mode=seasonality_mode,
            changepoint_prior_scale=changepoint_prior_scale,
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.95,  # 95% confidence interval
        )
        
        # Add custom seasonalities for Philippine holidays/peak seasons
        # Monthly seasonality
        model.add_seasonality(
            name='monthly',
            period=30.5,
            fourier_order=5
        )
        
        # Fit model
        app_logger.info("Training Prophet model...")
        model.fit(training_data)
        app_logger.info("Model training completed")
        
        return model
    
    def generate_forecast(
        self,
        model: Prophet,
        horizon_days: int = None
    ) -> pd.DataFrame:
        """
        Generate future predictions
        
        Args:
            model: Trained Prophet model
            horizon_days: Number of days to forecast
            
        Returns:
            DataFrame with predictions
        """
        horizon_days = horizon_days or self.settings.FORECAST_HORIZON_DAYS
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=horizon_days, freq='D')
        
        # Generate forecast
        app_logger.info(f"Generating {horizon_days}-day forecast...")
        forecast = model.predict(future)
        
        return forecast
    
    def aggregate_monthly_forecasts(
        self,
        forecast_df: pd.DataFrame
    ) -> List[Dict]:
        """
        Aggregate daily forecasts into monthly summaries
        
        Args:
            forecast_df: Prophet forecast dataframe
            
        Returns:
            List of monthly forecast summaries
        """
        # Add month column
        forecast_df['month'] = pd.to_datetime(forecast_df['ds']).dt.to_period('M')
        
        # Group by month
        monthly = forecast_df.groupby('month').agg({
            'yhat': 'mean',
            'yhat_lower': 'mean',
            'yhat_upper': 'mean'
        }).reset_index()
        
        # Convert to list of dicts
        monthly_forecasts = []
        for _, row in monthly.iterrows():
            monthly_forecasts.append({
                'month_start': row['month'].to_timestamp().date(),
                'month_end': (row['month'] + 1).to_timestamp().date() - timedelta(days=1),
                'point_forecast': float(row['yhat']),
                'lower_ci': float(row['yhat_lower']),
                'upper_ci': float(row['yhat_upper'])
            })
        
        return monthly_forecasts
    
    def save_forecast_run(
        self,
        route_id: int,
        model: Prophet,
        forecast_df: pd.DataFrame,
        train_start: date,
        train_end: date,
        horizon_days: int,
        currency_code: str = "PHP",
        user_id: Optional[int] = None
    ) -> int:
        """
        Save forecast run and results to database
        
        Args:
            route_id: Route ID
            model: Trained Prophet model
            forecast_df: Forecast DataFrame
            train_start: Training start date
            train_end: Training end date
            horizon_days: Forecast horizon
            currency_code: Currency code
            user_id: User who initiated (optional)
            
        Returns:
            forecast_run_id
        """
        # Create forecast run record
        forecast_run = ForecastRun(
            model_name="Prophet",
            run_scope="single_route",
            initiated_by=user_id,
            status="success",
            train_start_date=train_start,
            train_end_date=train_end,
            horizon_days=horizon_days,
            seasonalities={
                "yearly": True,
                "weekly": True,
                "monthly": True
            },
            finished_at=datetime.utcnow()
        )
        
        self.db.add(forecast_run)
        self.db.flush()  # Get forecast_run_id
        
        # Save model parameters
        model_params = ModelParameter(
            forecast_run_id=forecast_run.forecast_run_id,
            raw_params_json={
                "seasonality_mode": model.seasonality_mode,
                "changepoint_prior_scale": model.changepoint_prior_scale,
                "interval_width": model.interval_width
            },
            feature_list=["yearly", "weekly", "monthly"]
        )
        
        self.db.add(model_params)
        
        # Aggregate monthly forecasts
        monthly_forecasts = self.aggregate_monthly_forecasts(forecast_df)
        
        # Find cheapest month
        cheapest_idx = min(range(len(monthly_forecasts)), 
                          key=lambda i: monthly_forecasts[i]['point_forecast'])
        
        # Save forecast results
        for idx, monthly in enumerate(monthly_forecasts):
            result = ForecastResult(
                forecast_run_id=forecast_run.forecast_run_id,
                route_id=route_id,
                target_period_start=monthly['month_start'],
                target_period_end=monthly['month_end'],
                point_forecast=monthly['point_forecast'],
                lower_ci=monthly['lower_ci'],
                upper_ci=monthly['upper_ci'],
                currency_code=currency_code,
                model_version="1.0",
                is_cheapest_flag=(idx == cheapest_idx)
            )
            self.db.add(result)
        
        self.db.commit()
        
        app_logger.info(f"Saved forecast run {forecast_run.forecast_run_id} for route {route_id}")
        
        return forecast_run.forecast_run_id
    
    def run_forecast_for_route(
        self,
        route_id: int,
        lookback_days: int = 180,
        horizon_days: int = None,
        user_id: Optional[int] = None
    ) -> int:
        """
        Complete forecast pipeline for a route
        
        Args:
            route_id: Route to forecast
            lookback_days: Days of historical data to use
            horizon_days: Days to forecast ahead
            user_id: User initiating forecast
            
        Returns:
            forecast_run_id
        """
        try:
            # Calculate date range
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)
            
            # Prepare data
            training_data = self.prepare_training_data(route_id, start_date, end_date)
            
            if len(training_data) < 10:
                raise ValueError(f"Insufficient data for route {route_id}: only {len(training_data)} points")
            
            # Train model
            model = self.train_model(training_data)
            
            # Generate forecast
            forecast_df = self.generate_forecast(model, horizon_days)
            
            # Save results
            forecast_run_id = self.save_forecast_run(
                route_id=route_id,
                model=model,
                forecast_df=forecast_df,
                train_start=start_date,
                train_end=end_date,
                horizon_days=horizon_days or self.settings.FORECAST_HORIZON_DAYS,
                user_id=user_id
            )
            
            return forecast_run_id
            
        except Exception as e:
            app_logger.error(f"Forecast failed for route {route_id}: {e}")
            # Create failed run record
            failed_run = ForecastRun(
                model_name="Prophet",
                run_scope="single_route",
                initiated_by=user_id,
                status="failed",
                train_start_date=start_date,
                train_end_date=end_date,
                horizon_days=horizon_days or self.settings.FORECAST_HORIZON_DAYS,
                finished_at=datetime.utcnow()
            )
            self.db.add(failed_run)
            self.db.commit()
            
            raise
