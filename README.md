<div align="center">
  <img src="https://www.polysynergy.com/ps-color-logo-with-text.svg" alt="PolySynergy" width="300"/>
</div>

# PolySynergy Router

> 🚀 **Get Started**: This is part of the [PolySynergy Orchestrator](https://github.com/dionsnoeijen/polysynergy-orchestrator) - a visual workflow automation platform. Start there to set up the complete system and begin building AI agent workflows.

A high-performance, dynamic routing service built with FastAPI that serves as the main entry point for PolySynergy applications. The router automatically routes incoming HTTP requests to the appropriate backend services based on subdomain-based project and stage identification.

## 🚀 Overview

The PolySynergy Router is a core component of the [PolySynergy Orchestrator](https://github.com/dionsnoeijen/polysynergy-orchestrator) (coming soon). It acts as a reverse proxy that:

- Parses subdomains to identify projects and deployment stages
- Dynamically matches routes using configurable patterns
- Forwards requests to appropriate backend services (currently AWS Lambda)
- Provides a RESTful API for route management
- Caches route configurations for optimal performance

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   HTTP Request  │────▶│    Router    │────▶│ Lambda Function │
│ project-dev.com │     │              │     │  (Backend)      │
└─────────────────┘     │   - Parse    │     └─────────────────┘
                        │   - Match    │
                        │   - Forward  │     ┌─────────────────┐
                        │              │────▶│    DynamoDB     │
                        └──────────────┘     │ (Route Storage) │
                                             └─────────────────┘
```

## 📋 Features

- **Dynamic Route Matching**: Support for static and variable path segments
- **Multi-Stage Support**: Route different stages (dev, staging, prod) independently  
- **Variable Types**: String, number, UUID, and wildcard path parameters
- **Performance**: In-memory caching of route configurations
- **RESTful Management**: Full CRUD API for route configuration
- **Health Monitoring**: Built-in health check endpoint
- **Comprehensive Testing**: Unit and integration test coverage

## 🔧 Installation

### Prerequisites

- Python 3.11+
- pip
- AWS credentials (temporary - local storage coming soon)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/dionsnoeijen/polysynergy-orchestrator.git
cd orchestrator/router
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export AWS_REGION=eu-central-1
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export DYNAMODB_ROUTING_TABLE=poly_router_routing
```

## 🚀 Running the Application

### Development Mode

```bash
# Standard development mode with colored logs
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Enable debug logging
DEBUG_MODE=true uvicorn main:app --reload

# Custom log level
LOG_LEVEL=DEBUG uvicorn main:app --reload
```

### Production Mode

```bash
# Standard production mode
uvicorn main:app --host 0.0.0.0 --port 8080

# With JSON logs for log aggregation
JSON_LOGS=true uvicorn main:app --host 0.0.0.0 --port 8080

# With custom log level
LOG_LEVEL=WARNING JSON_LOGS=true uvicorn main:app
```

### Docker

```bash
# Build the image
docker build -t polysynergy-router .

# Run the container
docker run -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  polysynergy-router
```

## 📚 API Documentation

### Health Check

```http
GET /__internal/health
```

Returns:
```json
{"ok": true}
```

### Route Management

#### Create/Update Route

```http
POST /__internal/update-route
Content-Type: application/json

{
  "project_id": "my-project",
  "tenant_id": "tenant-123",
  "stage": "dev",
  "route": {
    "id": "api-users",
    "method": "GET",
    "require_api_key": false,
    "segments": [
      {"type": "static", "name": "api"},
      {"type": "static", "name": "users"},
      {"type": "variable", "name": "user_id", "variable_type": "number"}
    ],
    "node_setup_version_id": "v1.0.0",
    "tenant_id": "tenant-123"
  }
}
```

#### List Routes

```http
GET /__internal/routes/{project_id}
```

#### Deactivate Route

```http
POST /__internal/deactivate-route
Content-Type: application/json

{
  "project_id": "my-project",
  "stage": "dev",
  "route": {"id": "api-users"}
}
```

#### Delete Route

```http
DELETE /__internal/delete-route
Content-Type: application/json

{
  "project_id": "my-project",
  "route": {"id": "api-users"}
}
```

## 🛣️ Route Configuration

### Route Segments

Routes are defined using segments that can be either static or variable:

**Static Segments**: Exact string matches
```json
{"type": "static", "name": "api"}
```

**Variable Segments**: Dynamic path parameters with type validation
```json
{"type": "variable", "name": "id", "variable_type": "number"}
```

### Variable Types

- `string`: Any non-slash characters (default)
- `number`: Numeric values only
- `uuid`: UUID format validation
- `any`: Any characters including slashes

### Example Routes

1. **Simple API Route**: `/api/v1/status`
```json
{
  "segments": [
    {"type": "static", "name": "api"},
    {"type": "static", "name": "v1"},
    {"type": "static", "name": "status"}
  ]
}
```

2. **RESTful Resource**: `/users/{id}`
```json
{
  "segments": [
    {"type": "static", "name": "users"},
    {"type": "variable", "name": "id", "variable_type": "number"}
  ]
}
```

3. **Nested Resources**: `/projects/{project_id}/tasks/{task_id}`
```json
{
  "segments": [
    {"type": "static", "name": "projects"},
    {"type": "variable", "name": "project_id", "variable_type": "uuid"},
    {"type": "static", "name": "tasks"},
    {"type": "variable", "name": "task_id", "variable_type": "number"}
  ]
}
```

## 🧪 Testing

The project includes comprehensive unit and integration tests.

### Run All Tests

```bash
python run_tests.py
```

### Run Specific Test Types

```bash
# Unit tests only
python run_tests.py --unit

# Integration tests only
python run_tests.py --integration

# With coverage report
python run_tests.py --coverage
```

### Using pytest Directly

```bash
# Run all tests
pytest tests/

# Run with specific markers
pytest -m unit
pytest -m integration

# Run specific test file
pytest tests/unit/test_matcher.py -v
```

## 🔄 Request Flow

1. **Request Reception**: Client makes request to `project-stage.domain.com/path`
2. **Subdomain Parsing**: Extract `project_id` and `stage` from subdomain
3. **Route Lookup**: Query cached routes for project/stage combination
4. **Path Matching**: Match request path against route patterns
5. **Backend Invocation**: Forward request to configured backend service
6. **Response Proxying**: Return backend response to client

## 🐛 Debugging

The router includes comprehensive logging to help debug routing issues:

### Enable Debug Logging

```bash
# See all route matching attempts and patterns
DEBUG_MODE=true uvicorn main:app --reload
```

### Understanding 404 Errors

When you get a 404, the debug logs will show:
- The parsed project ID and stage
- Number of routes found for that project/stage
- Each route pattern tested against your path
- Available routes if no match is found

### Example Debug Output

```
INFO: Incoming request: GET /api/users/123
INFO: Parsed subdomain: project_id='myapp', stage='dev'
INFO: Found 3 routes for project='myapp', stage='dev'
INFO: Attempting to match path '/api/users/123' with method 'GET'
DEBUG: Path '/api/users/123' did not match pattern '^api/products$' for route 'products-list'
DEBUG: Path '/api/users/123' matched route 'users-detail' pattern '^api/users/(?P<id>\d+)$'
INFO: ✓ Route matched: 'users-detail' with variables: {'id': '123'}
```

### Request Tracking

Each request gets a unique ID in the `X-Request-ID` response header, making it easy to track requests through logs.

## 🚧 Roadmap

- [ ] **Local Storage**: Make DynamoDB optional and provide a default local alternative for development

## 🤝 Contributing

This project is currently under active development. Contributions will be welcome once the main PolySynergy Orchestrator repository is open-sourced.

## 📄 License

This project will be licensed under the same terms as the PolySynergy Orchestrator (license to be determined).

## 🔗 Related Projects

- **PolySynergy Orchestrator**: Main orchestration platform (coming soon)

## 📞 Support

For questions or issues, please wait for the public release of the PolySynergy Orchestrator project where you can:
- Open issues on GitHub
- Join our community discussions
- Read the documentation

---

Built with ❤️ by Dion Snoeijen