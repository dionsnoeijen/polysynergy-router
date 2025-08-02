# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
- Development: `uvicorn main:app --host 0.0.0.0 --port 8080 --reload --log-level debug`
- Production: `uvicorn main:app --host 0.0.0.0 --port 8080 --log-level debug`

### Docker
- Build: `docker build -t polysynergy-router .`
- Run: `docker run -p 8080:8080 polysynergy-router`

### Dependencies
- Install: `pip install -r requirements.txt`

### Testing
- Run all tests: `python run_tests.py` or `pytest tests/`
- Run unit tests only: `python run_tests.py --unit` or `pytest tests/unit/`
- Run integration tests only: `python run_tests.py --integration` or `pytest tests/integration/`
- Run with coverage: `python run_tests.py --coverage`
- Run tests excluding slow ones: `python run_tests.py --fast`
- Verbose output: `python run_tests.py --verbose`

### Logging
The router includes comprehensive logging to help debug routing issues:

- Development (colored output): `uvicorn main:app --reload`
- Production (JSON logs): `JSON_LOGS=true uvicorn main:app`
- Debug mode: `DEBUG_MODE=true uvicorn main:app`
- Custom log level: `LOG_LEVEL=DEBUG uvicorn main:app`

Key logged events:
- Request start/completion with duration and status
- Subdomain parsing results
- Route matching process (including regex patterns)
- DynamoDB queries and cache hits/misses
- Lambda invocation details
- Available routes when 404 occurs

Each request gets a unique request ID (X-Request-ID header) for tracking through logs.

## Architecture Overview

This is a **FastAPI-based routing service** that acts as a reverse proxy for the PolySynergy platform. It dynamically routes requests to AWS Lambda functions based on subdomain parsing and route matching.

### Core Flow
1. **Request Reception**: All requests hit the catch-all route handler at `api/router.py:35`
2. **Subdomain Parsing**: Extracts `project_id` and `stage` from subdomain format: `{project_id}-{stage}.domain.com`
3. **Route Resolution**: Queries DynamoDB for active routes matching the project/stage
4. **Route Matching**: Uses regex pattern matching to find the appropriate route and extract variables
5. **Lambda Invocation**: Forwards request to AWS Lambda function with structured payload
6. **Response Proxying**: Returns Lambda response to client

### Key Components

#### API Layer (`api/`)
- **`router.py`**: Main routing logic with catch-all handler that parses subdomains, matches routes, and invokes Lambda functions
- **`crud.py`**: Route management endpoints for updating, deactivating, and deleting routes from DynamoDB

#### Models (`models/`)
- **`route.py`**: Pydantic models defining route structure with segments (static/variable), methods, and metadata

#### Routing Engine (`routing/`)
- **`matcher.py`**: Converts route segments to regex patterns and matches incoming paths against routes
- **`cache.py`**: In-memory caching layer for DynamoDB route queries to improve performance

#### Configuration (`core/`)
- **`config.py`**: AWS credentials and service configuration via environment variables

### Route Segment Types
- **Static**: Exact string match (e.g., `/api/users`)
- **Variable**: Named capture groups with types:
  - `string`/`any`: `[^/]+` pattern
  - `number`: `\d+` pattern  
  - `uuid`: `[0-9a-fA-F-]{36}` pattern

### Environment Variables
- `AWS_REGION`: AWS region (default: eu-central-1)
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `DYNAMODB_ROUTING_TABLE`: DynamoDB table name (default: poly_router_routing)
- `ROUTER_PORT`: Application port (default: 8080)
- `LOG_LEVEL`: Logging level - DEBUG, INFO, WARNING, ERROR (default: INFO)
- `JSON_LOGS`: Enable JSON formatted logs for production (default: false)
- `DEBUG_MODE`: Enable debug mode with verbose logging (default: false)

### DynamoDB Schema
- **PK**: `routing#{project_id}`
- **SK**: `route#{route_id}`
- **Attributes**: method, segments, node_setup_version_id, tenant_id, active_stages, require_api_key

### Lambda Function Naming
Lambda functions follow the pattern: `node_setup_{node_setup_version_id}_{stage}`

### Internal Endpoints
- `/__internal/health`: Health check endpoint
- `/__internal/update-route`: Add/update routes
- `/__internal/deactivate-route`: Remove route from specific stage
- `/__internal/delete-route`: Delete route entirely
- `/__internal/routes/{project_id}`: List all routes for project

## Testing Framework

The project uses **pytest** with comprehensive unit and integration tests:

### Test Structure
- `tests/unit/`: Unit tests for individual components
  - `test_matcher.py`: Route matching logic and regex conversion
  - `test_router.py`: Subdomain parsing functionality  
  - `test_cache.py`: Caching mechanism with DynamoDB mocking
- `tests/integration/`: Integration tests for full workflows
  - `test_crud.py`: CRUD operations with mock DynamoDB
  - `test_main_router.py`: End-to-end routing flow with Lambda mocking
- `tests/conftest.py`: Shared fixtures and test configuration

### Test Dependencies
- **pytest**: Main testing framework with async support
- **pytest-mock**: Mocking utilities
- **moto**: AWS service mocking (DynamoDB, Lambda)
- **httpx**: HTTP client for FastAPI testing
- **TestClient**: FastAPI's built-in test client

### Key Test Features
- Mock AWS services (DynamoDB tables, Lambda functions)
- Comprehensive route matching validation
- Error handling and edge case coverage
- Cache behavior verification
- HTTP method and status code validation