# JVM Validation Service

Clojure orchestration service for the validation system. Uses Ring + Reitit for HTTP routing and babashka pods to communicate with the Python validation runner.

## Quick Start

### Development

Start a REPL:
```bash
clj -M:dev:repl
```

Run the service in development mode:
```clojure
(require '[validation-service.core :as core])
(core/-main)
```

### Building

Build an executable uberjar:
```bash
clj -T:build uber
```

This creates `target/validation-service-0.1.0-SNAPSHOT-standalone.jar` with embedded Jetty server.

### Running

Run the standalone jar:
```bash
java -jar target/validation-service-0.1.0-SNAPSHOT-standalone.jar
```

Or with custom config:
```bash
java -Dconfig.path=/path/to/config.edn -jar target/validation-service-0.1.0-SNAPSHOT-standalone.jar
```

### Testing

Run tests:
```bash
clj -M:test
```

## Project Structure

```
jvm-service/
├── src/
│   └── validation_service/
│       ├── core.clj              # Main entry point
│       ├── api/
│       │   ├── handlers.clj      # Request handlers
│       │   └── routes.clj        # Reitit route definitions
│       ├── orchestration/
│       │   ├── workflow.clj      # Validation workflow logic
│       │   └── coordination.clj  # Coordination service client
│       ├── runner/
│       │   ├── protocol.clj      # ValidationRunnerClient protocol
│       │   └── pods_client.clj   # Babashka pods implementation
│       └── monitoring/
│           └── metrics.clj       # Performance tracking
├── resources/
├── test/
├── deps.edn                      # Dependencies
├── build.clj                     # Build configuration
└── config.edn                    # Service configuration
```

## Configuration

Edit `config.edn` to configure:
- Service port and threading
- Python runner paths and timeouts
- Coordination service connection
- Logging and monitoring settings

## Dependencies

- **Clojure 1.12.0** - Language runtime
- **Ring 1.13.0** - HTTP server abstraction
- **Reitit 0.7.2** - Data-driven routing
- **babashka/pods** - Python runner communication
- **Cheshire** - JSON handling
- **Logback** - Logging backend

See `deps.edn` for complete dependency list.

## API Endpoints

### POST /api/v1/validate
Validate a single entity in real-time.

**Request:**
```json
{
  "entity_type": "loan",
  "entity_data": {
    "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
    "id": "LOAN-12345",
    ...
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "rule_id": "rule_001_v1",
      "status": "PASS",
      "message": "",
      "execution_time_ms": 1.23
    }
  ]
}
```

### GET /health
Health check endpoint.

### GET /metrics
Metrics endpoint (when monitoring enabled).

## Development Notes

- Uses Reitit for data-driven routing (not Compojure)
- Transport-agnostic design via ValidationRunnerClient protocol
- Python runner communication via babashka pods (bencode protocol)
- All business logic depends only on protocol, not transport implementation
