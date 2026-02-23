# Validation Service - REST API Example

A REST API web service that communicates with [validation-lib](https://github.com/judepayne/validation-lib) via JSON-RPC. This is a reference implementation showing how to expose validation capabilities via HTTP endpoints.

## Related Projects

- [validation-lib](https://github.com/judepayne/validation-lib) - Pure Python validation library with JSON-RPC server
- [validation-mcp-server](https://github.com/judepayne/validation-mcp-server) - MCP server for Claude Desktop integration

## What is This?

This is a thin web app layer (Clojure) that provides:
- REST API endpoints for validation operations
- Swagger/OpenAPI documentation
- Docker containerization
- Example deployment configuration

The core validation logic lives in validation-lib (Python). This service communicates with it via JSON-RPC over stdin/stdout.

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

## Prerequisites

Before running validation-service, you need to **clone validation-lib** into this directory:

```bash
# Clone validation-lib from GitHub
git clone https://github.com/judepayne/validation-lib.git
```

This creates a `validation-lib/` directory containing:
- The Python validation code
- Business logic (rules, schemas, entity helpers in `logic/`)
- Configuration files

**Why?** validation-service runs validation-lib as a subprocess and needs access to both the Python code and the business logic. The `validation-lib/` directory is git-ignored (not tracked in this repository) since it comes from the validation-lib repository.

**Requirements:**
- Clojure CLI (1.11+)
- Python 3.9+
- Git

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
- validation-lib (installed via pip from GitHub at build time, pinned to a specific SHA)
- This web service code
- All dependencies

Build the image:

```bash
# Basic build
docker build -t validation-service .

# Build with no cache (ensures fresh clone of validation-lib)
docker build --no-cache -t validation-service .

# Build using the helper script (auto-detects docker/podman)
./docker-build.sh
```

What happens during build:
1. Builder stage: Compiles Clojure service into uberjar
2. Runtime stage:
   - Installs Python 3 and pip
   - Installs validation-lib as a Python package via pip (from a pinned GitHub SHA)
   - Copies web service JAR
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
└── app.jar                      # Validation service uberjar

# validation-lib is installed as a Python package (pip), not a directory under /app.
# Business logic (rules, schemas) is fetched at runtime from the validation-logic
# GitHub repo via the URL configured in validation-lib's local-config.yaml.
# A web-config.edn must be present in the working directory (mount as a volume or
# bake into a derived image) to configure port, script-path, etc.
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

The service communicates with validation-lib via JSON-RPC over a subprocess.

### Architecture

```
validation-service (Clojure/Ring)
    ↓ JSON-RPC (stdin/stdout)
validation-lib (Python subprocess)
    ↓
Business Logic (rules, schemas, configs)
```

### How It Works

1. **Service Startup**: The service spawns validation-lib as a subprocess when it starts
2. **Auto-reload on startup**: `ValidationService.__init__()` automatically fetches fresh rules from GitHub if the local cache is older than `logic_cache_max_age_seconds` (default 30 min, configured in validation-lib's `local-config.yaml`). This means the subprocess always starts with up-to-date rules.
3. **JSON-RPC Communication**: All validation requests are sent via JSON-RPC 2.0 protocol over stdin/stdout
4. **Configuration Loading**: validation-lib loads its `local-config.yaml` which defines where business logic is located
5. **Long-lived Process**: The Python subprocess stays alive for the lifetime of the service (no startup cost per request). Mid-session cache staleness is checked automatically every 5 minutes.

### Configuration Files

**`resources/web-config.edn`** - Web service settings:

```clojure
{:service
 {:port 8080
  :host "0.0.0.0"}

 :validation_lib_py
 {:python_executable "python3"
  :script_path "../validation-lib"  ; Path to validation-lib directory
  :debug false}}
```

The `:validation_lib_py` configuration specifies:
- `:python_executable` - Python interpreter to use (default: python3)
- `:script_path` - Path to validation-lib directory (can be relative or absolute)
- `:debug` - Enable debug logging in the Python subprocess (default: false)

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
  -H "Content-Type": "application/json" \
  -d '{
    "entity_type": "loan",
    "schema_url": "https://bank.example.com/schemas/loan/v1.0.0",
    "ruleset_name": "quick"
  }' | jq
```

## Architecture

```
┌────────────────────────────────────────┐
│   validation-service (Clojure)         │
│   ┌──────────────────────────────────┐ │
│   │  Ring + Reitit HTTP Layer        │ │
│   │  - Routes & handlers             │ │
│   │  - Swagger UI                    │ │
│   │  - Request/response              │ │
│   └────────────┬─────────────────────┘ │
│                │                        │
│   ┌────────────▼─────────────────────┐ │
│   │  JSON-RPC Client                 │ │
│   │  - Subprocess management         │ │
│   │  - stdin/stdout communication    │ │
│   └────────────┬─────────────────────┘ │
└────────────────┼───────────────────────┘
                 │ JSON-RPC 2.0
                 │ (stdin/stdout)
┌────────────────▼───────────────────────┐
│   validation-lib (Python)           │
│   ┌──────────────────────────────────┐ │
│   │  JSON-RPC Server                 │ │
│   │  - Request parsing               │ │
│   │  - Method dispatching            │ │
│   └────────────┬─────────────────────┘ │
│                │                        │
│   ┌────────────▼─────────────────────┐ │
│   │  Core Validation Engine          │ │
│   │  - Rule execution                │ │
│   │  - Schema validation             │ │
│   │  - Configuration management      │ │
│   └──────────────────────────────────┘ │
└────────────────────────────────────────┘
```

This service is a thin HTTP wrapper around validation-lib. All validation logic lives in the Python library.

## Dependencies

The service depends on:
- **Clojure dependencies** (defined in deps.edn):
  - Ring + Reitit (HTTP server and routing)
  - Cheshire (JSON parsing for JSON-RPC)
  - Aero (configuration)
  - tools.logging (logging)
- **External process**:
  - validation-lib (Python) - Must be available at the configured `:script_path`
  - Python 3.x - Required to run validation-lib

The service does NOT have a Clojure dependency on validation-lib. Instead, it communicates with validation-lib via JSON-RPC over a subprocess.

## Deployment

### Local Development Setup

1. **Clone validation-lib** (or ensure it's available at the configured path):
   ```bash
   cd /path/to/projects/
   git clone https://github.com/judepayne/validation-lib
   ```

2. **Update web-config.edn** to point to validation-lib:
   ```clojure
   :validation_lib_py
   {:python_executable "python3"
    :script_path "../validation-lib"  ; Adjust path as needed
    :debug false}
   ```

3. **Run the service**:
   ```bash
   clojure -M:dev -m validation-service.core
   ```

### JAR Deployment

Build the uberjar:
```bash
clojure -T:build clean
clojure -T:build uber
```

Run the JAR:
```bash
# Ensure validation-lib is available
java -jar target/validation-service-0.1.0-SNAPSHOT-standalone.jar
```

**Note**: The JAR expects validation-lib to be available at the path specified in `web-config.edn`. You can either:
- Package validation-lib alongside the JAR
- Use an absolute path in the configuration
- Deploy as separate containers (microservices architecture)

### Docker Deployment

The Dockerfile should bundle:
- JVM service (this web app)
- validation-lib (cloned or copied into the image)
- Python 3.x runtime

Example multi-stage Dockerfile:
```dockerfile
FROM clojure:temurin-21-tools-deps AS builder
WORKDIR /build
COPY deps.edn build.clj ./
COPY src ./src
COPY resources ./resources
RUN clojure -T:build uber

FROM eclipse-temurin:21-jre
RUN apt-get update && apt-get install -y python3 python3-pip curl
WORKDIR /app
COPY --from=builder /build/target/*.jar app.jar
# Pin validation-lib to a specific SHA for reproducible builds
RUN pip3 install --no-cache-dir git+https://github.com/judepayne/validation-lib.git@dd2a841
ENV JAVA_OPTS="-Xmx512m"
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
```

### Environment-Specific Logic

validation-lib's `local-config.yaml` controls where business logic is loaded from:

- **Development**: Points to local logic/ directory
- **Production**: Can download logic from remote URL (e.g., S3, Git, HTTP)

See [validation-lib README](https://github.com/judepayne/validation-lib#configuration) for configuration details.

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
