from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import get_settings
from backend.core.logging import app_logger
from backend.database import init_db
from backend.api.auth import router as auth_router
from backend.api.flights import router as flights_router

settings = get_settings()

app = FastAPI(
    title="SmartLipad API",
    description="AI-powered airfare forecasting system for Philippine domestic flights",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    app_logger.info("Starting SmartLipad API...")
    app_logger.info(f"Debug mode: {settings.DEBUG}")
    app_logger.info(f"Database: {settings.DB_NAME}")
    init_db()
    app_logger.info("Database initialized successfully")

@app.on_event("shutdown")
async def shutdown_event():
    app_logger.info("Shutting down SmartLipad API...")

@app.get("/")
async def root():
    return {
        "message": "Welcome to SmartLipad API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational",
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(flights_router, prefix="/api/flights", tags=["Flights"])

if __name__ == "__main__":
    import uvicorn
    app_logger.info(f"Starting server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )
