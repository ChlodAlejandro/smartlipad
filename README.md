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

# 4. Initialize database
docker-compose exec backend python backend/scripts/init_db.py

# 5. Access API
# http://localhost:8000/docs
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

4. Initialize database:
   ```bash
   python backend/scripts/init_db.py
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

## Development

### Running Tests

**Run all tests:**
```bash
pytest
```

**Run specific test categories:**
```bash
# Unit tests only
pytest -m unit

# Integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run specific test file
pytest tests/test_auth.py

# Run specific test class
pytest tests/test_auth.py::TestUserRegistration

# Run specific test
pytest tests/test_auth.py::TestUserRegistration::test_register_new_user
```

**Run tests with coverage:**
```bash
# Generate coverage report
pytest --cov=backend --cov-report=html

# View HTML coverage report
# Open htmlcov/index.html in browser

# Terminal coverage report
pytest --cov=backend --cov-report=term-missing
```

**Run tests in parallel (faster):**
```bash
pip install pytest-xdist
pytest -n auto
```

**Test markers available:**
- `unit` - Unit tests
- `integration` - Integration tests
- `slow` - Slow-running tests
- `api` - API endpoint tests
- `database` - Database tests
- `scraper` - Scraper tests
- `forecast` - Forecasting tests
- `auth` - Authentication tests

### Code Quality

**Format code:**
```bash
black backend/ tests/
```

**Sort imports:**
```bash
isort backend/ tests/
```

**Lint code:**
```bash
flake8 backend/
```

**Type checking:**
```bash
mypy backend/
```

**Run all quality checks:**
```bash
black --check backend/ tests/
isort --check-only backend/ tests/
flake8 backend/
pytest --cov=backend
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## License

MIT License
