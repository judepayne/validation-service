# Validation Service - Quick Start Guide

## Implementation Complete ✓

All components have been implemented according to the plan:

### Components Implemented

- ✅ **Configuration** (`config.clj`) - Load config.edn with Aero
- ✅ **Core** (`core.clj`) - Main entry point with Jetty server
- ✅ **Coordination Client** (`orchestration/coordination.clj`) - Stub that logs and returns nil
- ✅ **Runner Protocol** (`runner/protocol.clj`) - Transport-agnostic interface
- ✅ **Pods Client** (`runner/pods_client.clj`) - Babashka pods implementation
- ✅ **Workflow** (`orchestration/workflow.clj`) - Orchestrates validation flow
- ✅ **Handlers** (`api/handlers.clj`) - Request handlers with error handling
- ✅ **Routes** (`api/routes.clj`) - Reitit data-driven routing with middleware
- ✅ **Integration Test** (`test/validation_service/integration_test.clj`)

### Endpoints Available

- `POST /api/v1/validate` - Execute validation rules
- `POST /api/v1/discover-rules` - Get rule metadata
- `GET /health` - Health check

---

## Quick Start

### 1. Verify Dependencies

Make sure you're in the `jvm-service` directory:
```bash
cd /Users/jude/Dropbox/Projects/validation-service/jvm-service
```

### 2. Test Compilation

Verify all namespaces compile:
```bash
clj -M:dev -e "(require '[validation-service.core :as core])"
```

Expected: No errors, just returns `nil`

### 3. Start the Server (REPL)

Start a REPL and run the server:
```bash
clj -M:dev:repl
```

In the REPL:
```clojure
(require '[validation-service.core :as core])
(core/-main)
```

Expected output:
```
INFO  validation-service.core - ===== Starting Validation Service =====
INFO  validation-service.config - Loading configuration...
INFO  validation-service.runner.pods-client - Loading Python runner pod
INFO  validation-service.runner.pods-client - Python runner pod loaded successfully
INFO  validation-service.core - Creating server on 0.0.0.0 : 8080
INFO  validation-service.core - Server started successfully
INFO  validation-service.core - Ready to accept requests
```

### 4. Test Health Endpoint

In another terminal:
```bash
curl http://localhost:8080/health
```

Expected:
```json
{"status":"healthy","timestamp":"2026-02-10T..."}
```

### 5. Test Validation Endpoint

```bash
curl -X POST http://localhost:8080/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "loan",
    "entity_data": {
      "$schema": "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json",
      "id": "LOAN-12345",
      "loan_number": "LN-001",
      "facility_id": "FAC-100",
      "financial": {
        "principal_amount": 100000,
        "outstanding_balance": 75000,
        "currency": "USD",
        "interest_rate": 0.05
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

Expected: JSON response with validation results

### 6. Test Discover Rules Endpoint

```bash
curl -X POST http://localhost:8080/api/v1/discover-rules \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "loan",
    "entity_data": {
      "$schema": "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json",
      "id": "TEST"
    },
    "ruleset_name": "quick"
  }'
```

Expected: JSON response with rule metadata

### 7. Run Integration Tests

**IMPORTANT:** Server must be running first (see step 3)

In another terminal:
```bash
cd jvm-service
clj -M:test -m validation-service.integration-test
```

Expected:
```
===== Integration Tests =====
Make sure the server is running on http://localhost:8080

=== Testing GET /health ===
Status: 200
...

=== Testing POST /api/v1/validate ===
Status: 200
...

=== Testing POST /api/v1/discover-rules ===
Status: 200
...

✓ All integration tests passed!
```

---

## Build Uberjar

```bash
# Clean
rm -rf target/

# Build
clj -T:build uber

# Verify
ls -lh target/validation-service-0.1.0-SNAPSHOT-standalone.jar

# Run standalone
java -jar target/validation-service-0.1.0-SNAPSHOT-standalone.jar
```

---

## Logs to Watch For

### Successful Startup Sequence:
1. ✅ Configuration loaded
2. ✅ Python runner pod loaded successfully
3. ✅ Server started on port 8080
4. ✅ Ready to accept requests

### Validation Request Flow:
1. ✅ Incoming request (validate)
2. ✅ Starting validation workflow
3. ✅ STUB: Coordination service called (this is expected!)
4. ✅ Validation workflow completed
5. ✅ Response sent

### What STUB Log Looks Like:
```
INFO  validation-service.orchestration.coordination - STUB: Coordination service called
  {:entity-type "loan",
   :vocabulary-terms [],
   :coordination-url "http://localhost:8081"}
```

This is **CORRECT** - the coordination service is stubbed to return nil and log calls.

---

## Troubleshooting

### Issue: "Configuration file not found"
**Solution:** Make sure you're running from `jvm-service/` directory or set config path:
```bash
java -Dconfig.path=/path/to/config.edn -jar target/*.jar
```

### Issue: "Failed to load Python runner pod"
**Solution:** Check that python-runner paths in config.edn are correct:
```clojure
:python_runner
{:executable "python3"
 :script_path "../python-runner/runner.py"
 :config_path "../python-runner/config.yaml"}
```

### Issue: Port 8080 already in use
**Solution:** Change port in config.edn or kill process on 8080:
```bash
lsof -ti:8080 | xargs kill -9
```

---

## Next Steps

1. ✅ **Test each endpoint** with curl or Postman
2. ✅ **Run integration tests** to verify end-to-end flow
3. ✅ **Build uberjar** and test standalone deployment
4. 🔄 **Replace coordination stub** with real implementation when ready
5. 🔄 **Add monitoring/metrics** (prometheus endpoint, etc.)
6. 🔄 **Add authentication/authorization** if needed

---

## Architecture Notes

### Transport Abstraction
The `ValidationRunnerClient` protocol allows swapping transports:
- Current: Babashka pods (bencode over stdin/stdout)
- Future: gRPC, HTTP, etc.
- Change only `runner/pods_client.clj`, rest of code unchanged

### Error Handling
All pod errors wrapped in `ex-info` with `:type` keyword:
- `:pod-communication-error` → 503 Service Unavailable
- `:pod-initialization-error` → Fatal startup error
- Other exceptions → 500 Internal Server Error

### Middleware Stack (bottom to top)
1. `wrap-request-logging` - Log requests/responses
2. `wrap-json-body` - Parse JSON request bodies
3. `wrap-json-response` - Serialize response bodies to JSON
4. `wrap-runner-client` - Inject runner client and config
5. Reitit router - Route matching and dispatch

---

**Implementation Status:** ✅ **COMPLETE AND READY TO TEST**
