"""
SmartLipad Backend - Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import get_settings
from backend.core.logging import app_logger
from backend.database import init_db

settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title="SmartLipad API",
    description="AI-powered airfare forecasting system for Philippine domestic flights",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    app_logger.info("Starting SmartLipad API...")
    app_logger.info(f"Debug mode: {settings.DEBUG}")
    app_logger.info(f"Database: {settings.DB_NAME}")
    
    # Initialize database
    try:
        init_db()
        app_logger.info("Database initialized successfully")
    except Exception as e:
        app_logger.error(f"Database initialization failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    app_logger.info("Shutting down SmartLipad API...")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to SmartLipad API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected"
    }


# Import and include routers
from backend.api import auth, flights

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(flights.router, prefix="/api/flights", tags=["Flights"])
# Additional routers to be added:
# app.include_router(forecasts.router, prefix="/api/forecasts", tags=["Forecasts"])
# app.include_router(comparisons.router, prefix="/api/comparisons", tags=["Comparisons"])
# app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


if __name__ == "__main__":
    import uvicorn
    
    app_logger.info(f"Starting server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )
