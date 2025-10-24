# SmartLipad Backend

![CI Status](https://github.com/yourusername/smartlipad/workflows/SmartLipad%20CI/badge.svg)
![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)

AI-powered airfare forecasting system for Philippine domestic flights.

## Features

- **Fare Forecasting**: Prophet-based time-series forecasting for airfare predictions
- **Data Scraping**: Automated collection of fare data from multiple sources
- **REST API**: FastAPI-based endpoints for flight search, predictions, and comparisons
- **User Management**: Authentication, authorization, and personalized fare comparisons
- **Admin Dashboard**: Data management, forecast runs, and system monitoring

## Project Structure

```
smartlipad/
├── backend/
│   ├── api/              # FastAPI application and routes
│   ├── core/             # Core configuration and utilities
│   ├── models/           # SQLAlchemy database models
│   ├── schemas/          # Pydantic schemas for validation
│   ├── services/         # Business logic and services
│   ├── scrapers/         # Web scraping modules
│   ├── forecasting/      # Prophet-based forecasting engine
│   └── main.py           # Application entry point
├── alembic/              # Database migrations
├── tests/                # Unit and integration tests
├── logs/                 # Application logs
├── requirements.txt      # Python dependencies
└── .env                  # Environment variables (not in git)
```

## Setup

### Option 1: Docker Setup (Recommended)

**Prerequisites:**
- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose v2.0+

**Quick Start:**
```bash
# 1. Copy environment file
copy .env.docker .env

# 2. Edit .env and set passwords and SECRET_KEY

# 3. Start services
docker-compose up -d
```
---

### Option 2: Local Development Setup

**Prerequisites:**
- Python 3.11+
- MariaDB/MySQL 8.0+
- Redis 6.0+ (for task queue)

**Installation:**

1. Create virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and configure:
   ```bash
   copy .env.example .env
   ```

**Running the Application:**

Development server:
```bash
python backend/main.py
```

Or with uvicorn:
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc