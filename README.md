# Validation Service - REST API Example

A REST API web service wrapper around the [validation-lib](https://github.com/judepayne/validation-lib) library. This is a reference implementation showing how to expose validation capabilities via HTTP endpoints.

## Related Projects

- [validation-lib](https://github.com/judepayne/validation-lib) - Core validation library (Clojure + Python)
- [validation-mcp-server](https://github.com/judepayne/validation-mcp-server) - MCP server for Claude Desktop integration

## What is This?

This is a thin web app layer that provides:
- REST API endpoints for validation operations
- Swagger/OpenAPI documentation
- Docker containerization
- Example deployment configuration

The core validation logic lives in validation-lib. This service just wraps it with HTTP.

## REST API Endpoints

`POST /api/v1/validate`
Validates a single entity against configured rules.

`POST /api/v1/discover-rules`
Returns metadata about available rules for an entity type.

`GET /api/v1/discover-rulesets`
Returns metadata and statistics for all available rulesets.

`POST /api/v1/batch`
Validates multiple entities in a single request (supports mixed entity types).

`POST /api/v1/batch-file`
Validates entities loaded from a file URI (file://, http://, https://).

`GET /health`
Service health check endpoint.

Interactive API Documentation: http://localhost:8080/swagger-ui

## Quick Start

### Local Development

Using convenience scripts:

```bash
# Start the server
./run_server.sh

# In another terminal, stop the server
./stop_server.sh
```

Using Clojure directly:

```bash
# Start the service
clojure -M:dev -m validation-service.core

# Access Swagger UI
open http://localhost:8080/swagger-ui

# Health check
curl http://localhost:8080/health

# Stop the server (find and kill process on port 8080)
lsof -ti :8080 | xargs kill -9
```

### Docker

The Dockerfile creates a self-contained image that includes:
- JVM runtime (Eclipse Temurin 21)
- Python 3 + pip
- validation-lib (cloned from GitHub at build time)
- This web service code
- All dependencies

Build the image:

```bash
# Basic build
docker build -t validation-service .

# Build with specific validation-lib version (edit Dockerfile first to change SHA)
docker build -t validation-service:v1.0 .

# Build with no cache (ensures fresh clone of validation-lib)
docker build --no-cache -t validation-service .

# Build using the helper script (auto-detects docker/podman)
./docker-build.sh
```

What happens during build:
1. Builder stage: Downloads Clojure dependencies via git (validation-lib)
2. Runtime stage:
   - Installs Python 3 and Git
   - Clones validation-lib from GitHub
   - Installs Python dependencies (jsonschema, pyyaml, etc.)
   - Copies web service code and configs
   - Sets up directory structure

Run the container:

```bash
# Run in detached mode
docker run -d \
  --name validation-service \
  -p 8080:8080 \
  validation-service

# Run with custom memory limits
docker run -d \
  --name validation-service \
  -p 8080:8080 \
  -e JAVA_OPTS="-Xmx1g -Xms512m" \
  validation-service

# Run with logs visible (foreground)
docker run --rm \
  --name validation-service \
  -p 8080:8080 \
  validation-service

# Run with custom port
docker run -d \
  --name validation-service \
  -p 3000:8080 \
  validation-service
```

Test the running container:

```bash
# Health check
curl http://localhost:8080/health

# Swagger UI
open http://localhost:8080/swagger-ui

# View logs
docker logs validation-service

# Follow logs
docker logs -f validation-service

# Execute shell in container
docker exec -it validation-service /bin/bash
```

Stop and cleanup:

```bash
# Stop the container
docker stop validation-service

# Remove the container
docker rm validation-service

# Remove the image
docker rmi validation-service

# One-liner: stop and remove
docker rm -f validation-service
```

Container structure:
```
/app/
├── validation-lib/              # Cloned from GitHub
│   ├── python-runner/
│   │   ├── runner.py
│   │   ├── local-config.yaml
│   │   └── core/
│   └── logic/
│       ├── business-config.yaml
│       ├── rules/
│       └── models/
├── src/                         # Web service source
│   └── validation_service/
├── resources/                   # Configs
│   └── web-config.edn
└── deps.edn
```

Environment variables:
- `JAVA_OPTS`: JVM options (default: `-Xmx512m -Xms256m`)
- `PYTHONUNBUFFERED`: Python logging (default: `1`)

Image size: ~500-600 MB (includes JRE, Python, dependencies)

Note for production: For better image size and security, consider:
- Using Alpine-based images where possible
- Multi-stage builds to exclude build tools
- Separate Python runner container (microservices architecture)

## Configuration

The service uses validation-lib with automatic configuration - no manual setup required.

### How It Works

validation-lib automatically discovers and configures the Python runner at startup:

1. Non-JAR (development): Uses python-runner directly from `.gitlibs/` where Clojure downloads the git dependency
2. JAR (production): Extracts python-runner and logic from JAR to `~/.cache/validation-lib/` on first run

The bundled `local-config.yaml` from validation-lib defines where business logic (rules, schemas) is located. This can be:
- Local path (development): Points to logic/ in the git dependency
- Remote URL (production): Downloads logic from a central repository at runtime

See [validation-lib README](https://github.com/judepayne/validation-lib#how-the-library-manages-python-dependencies-in-your-app) for details on JAR deployment modes.

### JAR Build Configuration

The `build.clj` file copies both python-runner/ and logic/ from validation-lib into the JAR during compilation:

```clojure
;; build.clj extracts from validation-lib git dependency
(copy-python-runner basis class-dir)  ; Copies python-runner files
(copy-logic basis class-dir)          ; Copies logic files (if using local mode)
```

### Web Service Configuration

Web service settings in `resources/web-config.edn`:

```clojure
{:server
 {:port 8080
  :host "0.0.0.0"}

 :coordination_service  ; Not implemented in POC
 {:base_url "http://localhost:8081"
  :timeout_ms 5000}}
```

## Example Requests

### Validate a Loan

```bash
curl -X POST http://localhost:8080/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "loan",
    "entity_data": {
      "$schema": "file:///path/to/loan.schema.json",
      "id": "LOAN-001",
      "loan_number": "LN-001",
      "facility_id": "FAC-100",
      "financial": {
        "principal_amount": 100000,
        "interest_rate": 0.045,
        "currency": "USD"
      },
      "dates": {
        "origination_date": "2024-01-01",
        "maturity_date": "2025-01-01"
      },
      "status": "active"
    },
    "ruleset_name": "quick"
  }'
```

### Discover Available Rulesets

```bash
curl http://localhost:8080/api/v1/discover-rulesets | jq
```

### Discover Rules for Loan

```bash
curl -X POST http://localhost:8080/api/v1/discover-rules \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "loan",
    "entity_data": {
      "$schema": "file:///path/to/loan.schema.json"
    },
    "ruleset_name": "quick"
  }' | jq
```

## Architecture

```
┌──────────────────────────────────┐
│   validation-service (this)      │
│   ┌────────────────────────────┐ │
│   │  Ring + Reitit HTTP Layer  │ │
│   │  - Routes & handlers       │ │
│   │  - Swagger UI              │ │
│   │  - Request/response        │ │
│   └────────────┬───────────────┘ │
└────────────────┼─────────────────┘
                 │
                 │ ValidationService Protocol
                 │
┌────────────────▼─────────────────┐
│       validation-lib             │
│   ┌──────────────────────────┐   │
│   │  Core Validation Engine  │   │
│   │  - Workflow orchestration│   │
│   │  - JSON-RPC client       │   │
│   │  - Python runner mgmt    │   │
│   └──────────────────────────┘   │
└──────────────────────────────────┘
```

This service is a thin wrapper - all validation logic lives in validation-lib.

## Dependencies

The service depends on:
- validation-lib (via git deps)
- Ring + Reitit (HTTP server and routing)
- Python 3.x (for rule execution via validation-lib)

Current dependency in `deps.edn`:
```clojure
{:deps
 {validation-lib/validation-lib
  {:git/url "https://github.com/judepayne/validation-lib"
   :git/sha "7e4c2389913c864518c2707535219a89cb256686"}}}
```

## Deployment

### Docker Deployment

The Dockerfile bundles:
- JVM service (this web app)
- Python runner (from validation-lib)
- Example logic folder (rules + schemas)

```dockerfile
# Multi-stage build for minimal image size
FROM clojure:temurin-21-tools-deps AS builder
# ... build steps

FROM eclipse-temurin:21-jre-alpine
# ... runtime steps
```

### Environment-Specific Logic

validation-lib's bundled `local-config.yaml` controls where business logic is loaded from. For different environments, validation-lib can be configured with different logic sources:

- Development: Uses local logic/ from the git dependency
- Production: Can download logic from remote URL (e.g., `https://rules-repo.example.com/prod/logic`)

This is configured in validation-lib, not in this service. See [validation-lib deployment modes](https://github.com/judepayne/validation-lib#jar-deployment-production) for details.

## Extending This Service

### Add New Endpoints

1. Define schema in `src/validation_service/api/schemas.clj`
2. Add handler in `src/validation_service/api/handlers.clj`
3. Register route in `src/validation_service/api/routes.clj`

Example:
```clojure
;; routes.clj
["/api/v1/my-endpoint"
 {:post {:summary "My custom endpoint"
         :parameters {:body ::schemas/my-request}
         :responses {200 {:body ::schemas/my-response}}
         :handler handlers/my-handler}}]
```

### Middleware

Add custom middleware in `routes.clj`:

```clojure
(def app-handler
  (ring/ring-handler
    router
    (constantly {:status 404})
    {:middleware [my-custom-middleware]}))
```

## Testing

### Integration Tests (Babashka)

Run the full integration test suite that starts the server and tests all endpoints:

```bash
# Requires babashka: brew install babashka/brew/babashka
./test.bb
```

The test script will:
1. Start the validation-service
2. Wait for it to be ready
3. Test all API endpoints:
   - `/health` - Health check
   - `/api/v1/discover-rulesets` - Get available rulesets
   - `/api/v1/discover-rules` - Discover rules for loan entity
   - `/api/v1/validate` - Validate a sample loan
   - `/api/v1/batch` - Batch validate entities
4. Stop the server
5. Report results

Expected output:
```
======================================================================
Validation Service Integration Tests
======================================================================
✓ Health check
✓ Discover rulesets
✓ Discover rules
✓ Validate entity
✓ Batch validate
======================================================================
Test Summary
======================================================================
Passed: 5
Failed: 0
======================================================================
✓ All tests passed!
```

## License

MIT © Jude Payne 2026

## See Also

- [validation-lib](https://github.com/judepayne/validation-lib) for library usage, rule development, and architecture
- [validation-mcp-server](https://github.com/judepayne/validation-mcp-server) for Claude Desktop integration example
