# Validation Service - Technical Design

## Document Purpose

This document describes the technical architecture and implementation design for the commercial bank loan validation service. It is intended for software engineers, architects, and technical stakeholders.

For functional requirements and business context, refer to DESIGN.md.

## Implementation Phases

The implementation follows two phases:

**Phase 1 - POC/Prototype:**
- JVM Service: Clojure
- Rule Runner: Python
- Communication: Babashka pods (bencode protocol)
- Data Model: JSON Schema validated using Python `jsonschema` library
- Schema Storage: Local `models/` folder (versioned alongside code)
- Packaging: Docker container (single image with Clojure + Python)
- Goal: Validate architecture and prove performance characteristics

**Phase 2 - Production/Enterprise:**
- JVM Service: Java (Spring Boot or similar)
- Rule Runner: Python (unchanged)
- Communication: Bencode or gRPC (to be determined based on POC learnings)
- Data Model: To be determined (likely JSON Schema, but other options like Pydantic or Protocol Buffers may be considered)
- Packaging: Docker container with orchestration (Kubernetes, Docker Swarm, or cloud-native)
- Goal: Production-ready with enterprise tooling and support

## Key Design Principles

### Transport Layer Abstraction

**Principle:** Both JVM and Python implementations abstract the transport/communication layer behind well-defined interfaces (Clojure protocols / Java interfaces / Python abstract base classes).

**Rationale:**
- Enable seamless migration between communication protocols (pods → gRPC)
- Support gradual transition or A/B testing of different transports
- Allow business logic to be tested independently of transport mechanism
- Simplify future enhancements (e.g., adding HTTP/REST or message queue support)

**Implementation:**
- **JVM Side:** `ValidationRunnerClient` protocol/interface with pluggable implementations (`PodsRunnerClient`, `GrpcRunnerClient`)
- **Python Side:** `TransportHandler` abstract base class with pluggable implementations (`PodsTransportHandler`, `GrpcTransportHandler`)
- **Core Logic:** Validation orchestration and rule execution logic have zero dependencies on specific transports

**Benefits:**
- POC can use simple babashka pods without committing to it long-term
- Migration decisions can be deferred until performance requirements are validated
- Transport changes require minimal code modifications
- Clear boundaries enable parallel development (transport vs. business logic)

See the "Communication Protocol" and "Transport Abstraction Layer" sections for detailed implementation examples.

### Data Model Abstraction

**Principle:** Validation rules do not access entity data (deal, facility, loan) directly via raw JSON/dict structures. Instead, they use typed helper classes that provide stable getter methods for data extraction.

**Rationale:**
- The enterprise data model for deals, facilities, and loans evolves under change control
- Model restructuring (field renaming, nesting changes, data type changes) is common
- Direct JSON access couples rules tightly to model structure
- Model changes would require updating all rules that access modified fields
- Abstraction layer isolates rules from structural changes

**Implementation:**
- **Python Helper Classes:** `Loan`, `Facility`, `Deal` classes wrap raw entity data
- **Stable Interface:** Helper classes provide getter methods (e.g., `loan.amount`, `facility.limit`)
- **Model Changes:** Only helper classes updated when model structure changes
- **New Fields:** Helper classes extended when new data added to model (for new rules)
- **Rules Unchanged:** Existing rules continue working when model restructured

**Example Without Abstraction (Fragile):**
```python
# Direct JSON access - breaks when model changes
loan_amount = self.entity_data.get("amount")
currency = self.entity_data.get("currency")
maturity = self.entity_data.get("maturityDate")

# What if model changes to nested structure?
# loan_amount = self.entity_data.get("financial").get("principalAmount")
# All rules must be updated!
```

**Example With Abstraction (Robust):**
```python
# Helper class provides stable interface
loan_amount = self.loan.amount
currency = self.loan.currency
maturity = self.loan.maturity_date

# Model restructured? Only helper class updated:
# class LoanV1:
#     @property
#     def amount(self):
#         return self.data.get("financial", {}).get("principalAmount")
# Rules remain unchanged!
```

**Benefits:**
- **Decoupling:** Rules isolated from model structure changes
- **Maintainability:** Model evolution doesn't break existing rules
- **Readability:** `loan.amount` clearer than `entity_data.get("amount")`
- **Type Safety:** Helper classes can provide type hints for IDE support
- **Computed Properties:** Helper can expose derived/calculated fields
- **Validation:** Helper can enforce data access patterns

See the "Entity Helper Classes" section for detailed implementation.

## System Architecture

### High-Level Components

```
           ┌─────────────┐
           │   Client    │
           │   Systems   │
           └──────┬──────┘
                  │
                  │ HTTP/REST
                  │
┌─────────────────▼──────────────────────────────┐
│                                                │
│       JVM Orchestration Service                │
│           (Clojure → Java)                     │
│                                                │
│  ┌───────────────────────────────────────┐     │
│  │  Spawn & Manage Python Runner Process │     │
│  └───────────────────────────────────────┘     │
│                                                │
└─────┬─────────────────────┬────────────────────┘
      │                     │
      │ Bencode/Pods        │ HTTP/REST
      │                     │
┌─────▼──────────┐   ┌──────▼────────-──────┐
│                │   │                      │
│  Python Rule   │   │  Coordination        │
│    Runner      │   │    Service           │
│                │   │    (External)        │
│  ┌──────────┐  │   │                      │
│  │  Rules   │  │   │  Provides additional │
│  │          │  │   │  data for validation │
│  │ • loan/  │  │   │                      │
│  │ • fac... │  │   └──────────────────────┘
│  │ • deal/  │  │
│  └──────────┘  │
│                │
└────────────────┘
```

### Component Responsibilities

**JVM Orchestration Service:**
- Expose REST API for inline and batch validation (`/api/v1/validate`, `/api/v1/batch`, `/api/v1/batch-file`)
- Orchestrate two-phase validation workflow
- **Single persistent Python runner pod** - Created at service startup, reused for all requests
- Call coordination service to fetch required data (currently stubbed)
- Aggregate and return validation results
- Support flexible output modes (HTTP response or file output)
- Normalize relative file:// URIs to absolute paths for Python compatibility
- Monitor and log performance metrics

**Python Rule Runner:**
- **Rule-set agnostic execution engine** - executes named rule sets without semantic knowledge
- Load configuration defining named rule sets (e.g., "quick_rules", "thorough_rules", "audit_rules")
- Discover and dynamically load rule classes
- Expose functions via pod interface:
  - `get_required_data(entity_type, schema_url, ruleset_name)`: Introspect rules and return needed data
  - `validate(entity_type, entity_data, ruleset_name, required_data)`: Execute rules and return hierarchical results
  - `discover_rules(entity_type, entity_data, ruleset_name)`: Return comprehensive rule metadata
- Execute rules sequentially, respecting hierarchy
- Cache entity and required data during execution
- Handle rule execution errors gracefully

**Architectural Separation:**
- JVM Service: Controls **when** (inline/batch mode) and **which rule set** to use
- Python Runner: Executes the specified rule set, agnostic to JVM orchestration mode
- Example: JVM inline mode → passes `ruleset_name="quick"` for real-time validation
- Example: JVM batch mode → passes `ruleset_name="thorough"` for comprehensive validation

**Coordination Service (External):**
- Provide additional data required by validation rules
- Support queries by vocabulary terms (parent, all_siblings, etc.)
- Return structured data for hierarchical and related entities

## Communication Protocol

### Babashka Pods (POC Phase)

Babashka pods enable language interoperability via a bencode-based RPC protocol over stdin/stdout.

**Protocol Characteristics:**
- Binary encoding (bencode - BitTorrent format)
- Bidirectional RPC over stdin/stdout
- Stateful: Process remains alive across multiple calls (single pod serves all requests)
- Function invocation model (not just data exchange)

**Message Format:**
- Request: `{op: "invoke", id: <request-id>, var: <function-name>, args: <args-dict>}`
- Response: `{id: <request-id>, value: <return-value>}` or `{id: <request-id>, error: <error-msg>}`

**Python Runner Functions:**

```clojure
;; Phase 1: Get required data
(pods/invoke "python-runner" "get_required_data"
  {:entity_type "loan"
   :entity_data {...}
   :mode "inline"})
;; Returns: ["parent", "all_siblings", "client_reference_data"]

;; Phase 2: Run validation
(pods/invoke "python-runner" "validate"
  {:entity_type "loan"
   :entity_data {...}
   :mode "inline"
   :required_data {...}})
;; Returns: hierarchical results structure
```

**Libraries:**
- Clojure: `babashka/pods` library
- Python: `bencode` library (e.g., `bencode.py`)

### Transport Abstraction Layer

**Design Principle:** To facilitate future migration from babashka pods to alternative transport mechanisms (e.g., gRPC, HTTP/REST), both the Clojure/Java and Python implementations will abstract the transport layer behind well-defined interfaces/protocols.

#### Clojure Side Abstraction

The JVM service will define a protocol (Clojure) / interface (Java) for communicating with the Python runner:

```clojure
;; Protocol definition
(defprotocol ValidationRunnerClient
  "Abstract interface for communicating with Python validation runner"
  (get-required-data [this entity-type entity-data mode]
    "Phase 1: Query Python runner for required data vocabulary terms")
  (validate [this entity-type entity-data mode required-data]
    "Phase 2: Execute validation rules and return hierarchical results")
  (shutdown [this]
    "Clean up resources and shutdown connection"))

;; Babashka Pods implementation
(defrecord PodsRunnerClient [pod-instance]
  ValidationRunnerClient
  (get-required-data [this entity-type entity-data mode]
    (pods/invoke pod-instance "get_required_data"
      {:entity_type entity-type
       :entity_data entity-data
       :mode mode}))

  (validate [this entity-type entity-data mode required-data]
    (pods/invoke pod-instance "validate"
      {:entity_type entity-type
       :entity_data entity-data
       :mode mode
       :required_data required-data}))

  (shutdown [this]
    (pods/unload-pod pod-instance)))

;; Factory function
(defn create-runner-client [config]
  (->PodsRunnerClient (pods/load-pod config)))
```

**Future gRPC implementation would be:**
```clojure
(defrecord GrpcRunnerClient [grpc-channel]
  ValidationRunnerClient
  (get-required-data [this entity-type entity-data mode]
    ;; gRPC call implementation
    ...)

  (validate [this entity-type entity-data mode required-data]
    ;; gRPC call implementation
    ...)

  (shutdown [this]
    (.shutdown grpc-channel)))
```

**Java equivalent (for production phase):**
```java
public interface ValidationRunnerClient {
    List<String> getRequiredData(String entityType,
                                  Map<String, Object> entityData,
                                  String mode);

    ValidationResults validate(String entityType,
                                Map<String, Object> entityData,
                                String mode,
                                Map<String, Object> requiredData);

    void shutdown();
}

public class PodsRunnerClient implements ValidationRunnerClient {
    // Bencode/pods implementation
}

public class GrpcRunnerClient implements ValidationRunnerClient {
    // gRPC implementation
}
```

#### Python Side Abstraction

The Python runner will separate transport concerns from business logic:

```python
# transport/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class TransportHandler(ABC):
    """Abstract base class for transport layer"""

    @abstractmethod
    def start(self):
        """Start listening for requests"""
        pass

    @abstractmethod
    def send_response(self, request_id: str, result: Any):
        """Send successful response"""
        pass

    @abstractmethod
    def send_error(self, request_id: str, error: str):
        """Send error response"""
        pass

    @abstractmethod
    def receive_request(self) -> tuple[str, str, Dict[str, Any]]:
        """Receive next request, returns (request_id, function_name, args)"""
        pass

# transport/pods_transport.py
import bencode
import sys

class PodsTransportHandler(TransportHandler):
    """Babashka pods transport implementation"""

    def start(self):
        # Initialize stdin/stdout handling
        pass

    def send_response(self, request_id: str, result: Any):
        response = {"id": request_id, "value": result}
        sys.stdout.buffer.write(bencode.encode(response))
        sys.stdout.buffer.flush()

    def send_error(self, request_id: str, error: str):
        response = {"id": request_id, "error": error}
        sys.stdout.buffer.write(bencode.encode(response))
        sys.stdout.buffer.flush()

    def receive_request(self) -> tuple[str, str, Dict[str, Any]]:
        msg = bencode.decode(sys.stdin.buffer)
        return (msg.get("id"), msg.get("var"), msg.get("args", {}))

# transport/grpc_transport.py (future implementation)
class GrpcTransportHandler(TransportHandler):
    """gRPC transport implementation"""

    def start(self):
        # Start gRPC server
        pass

    def send_response(self, request_id: str, result: Any):
        # Send gRPC response
        pass

    # ... other methods

# runner.py (main entry point)
from transport.pods_transport import PodsTransportHandler
from validation_engine import ValidationEngine

def main():
    # Transport layer is injected
    transport = PodsTransportHandler()  # Or: GrpcTransportHandler()
    engine = ValidationEngine(config_path="./config.yaml")

    transport.start()

    while True:
        request_id, function_name, args = transport.receive_request()

        try:
            if function_name == "get_required_data":
                result = engine.get_required_data(
                    args["entity_type"],
                    args["entity_data"],
                    args["mode"]
                )
            elif function_name == "validate":
                result = engine.validate(
                    args["entity_type"],
                    args["entity_data"],
                    args["mode"],
                    args["required_data"]
                )
            else:
                raise ValueError(f"Unknown function: {function_name}")

            transport.send_response(request_id, result)

        except Exception as e:
            transport.send_error(request_id, str(e))

if __name__ == "__main__":
    main()
```

#### Benefits of Transport Abstraction

**For POC Phase:**
- Clean separation of concerns
- Easier to unit test business logic (mock transport)
- Transport layer can be tested independently

**For Migration:**
- Swap transport implementation without touching business logic
- Both transports can coexist during transition (A/B testing)
- Gradual rollout: test gRPC in staging while pods runs in production
- Minimal code changes required

**For Maintenance:**
- Add new transport options easily (HTTP/REST, message queue, etc.)
- Transport-specific optimizations don't affect core logic
- Clear boundaries for debugging and monitoring

### Migration to Java

With the transport abstraction layer in place, migration from Clojure to Java is straightforward:

**Step 1 - Migrate Core Logic:**
- Implement Java version of orchestration service
- Implement `ValidationRunnerClient` interface in Java
- Keep using `PodsRunnerClient` implementation (Option A below)

**Step 2 - Choose Transport Evolution Path:**

**Option A - Continue with Bencode (Low Risk):**
- Implement bencode protocol in Java (straightforward)
- Keep identical interface to POC
- No changes to Python runner
- Libraries available: `bencode-java` or custom implementation
- **When to choose:** Babashka pods performance is acceptable in POC

**Option B - Migrate to gRPC (Performance):**
- Define `.proto` service definition
- Implement `GrpcRunnerClient` in Java
- Implement `GrpcTransportHandler` in Python (already abstracted)
- Run Python runner as long-running service
- Better tooling, monitoring, and streaming support
- **When to choose:** POC identifies performance issues with process spawning

**Option C - Hybrid Approach:**
- Support both transports simultaneously
- Use feature flag to control which transport is used
- Gradual migration entity-type by entity-type
- Fallback to pods if gRPC service unavailable

**Recommendation:**

1. **POC Phase:** Use babashka pods with transport abstraction
2. **Production Decision Point:** Based on POC performance results:
   - If sub-second target met easily → Option A (continue with bencode in Java)
   - If performance tight or batch mode slow → Option B (migrate to gRPC)
3. Transport abstraction makes either path straightforward

## JVM Orchestration Service

### Technology Stack

**POC:**
- Clojure 1.11+
- Ring/Reitit for HTTP (data-driven routing)
- babashka/pods for Python communication
- cheshire for JSON handling
- clojure.tools.logging

**Production:**
- Java 17+
- Spring Boot 3.x
- Either bencode library or gRPC
- Jackson for JSON
- SLF4J/Logback for logging
- Micrometer for metrics

### Architecture with Transport Abstraction

The JVM service uses the `ValidationRunnerClient` protocol/interface (defined in the Communication Protocol section) to abstract Python runner communication. This enables:

1. **Swapping transports** without changing orchestration logic
2. **Testing** with mock implementations
3. **Gradual migration** from pods to gRPC
4. **Clean separation** between business logic and transport concerns

**Clojure Implementation Structure:**
```
src/
├── validation_service/
│   ├── core.clj                  # Main application entry point
│   ├── api/
│   │   ├── handlers.clj          # Request handler functions
│   │   └── routes.clj            # Reitit route definitions (data-driven)
│   ├── orchestration/
│   │   ├── workflow.clj          # Validation workflow logic
│   │   └── coordination.clj      # Coordination service client
│   ├── runner/
│   │   ├── protocol.clj          # ValidationRunnerClient protocol
│   │   ├── pods_client.clj       # Babashka pods implementation
│   │   └── grpc_client.clj       # gRPC implementation (future)
│   └── monitoring/
│       └── metrics.clj            # Performance tracking
```

**Java Implementation Structure:**
```
src/main/java/
├── com/bank/validation/
│   ├── Application.java           # Spring Boot application
│   ├── api/
│   │   └── ValidationController.java
│   ├── orchestration/
│   │   ├── ValidationWorkflow.java
│   │   └── CoordinationServiceClient.java
│   ├── runner/
│   │   ├── ValidationRunnerClient.java     # Interface
│   │   ├── PodsRunnerClient.java           # Bencode impl
│   │   └── GrpcRunnerClient.java           # gRPC impl
│   └── monitoring/
│       └── MetricsCollector.java
```

All orchestration code depends only on the `ValidationRunnerClient` abstraction, never on specific transport implementations.

### Configuration

```yaml
# config.yaml

service:
  port: 8080
  max_concurrent_validations: 100

python_runner:
  executable: "python3"
  script_path: "./python-runner/runner.py"
  config_path: "./python-runner/config.yaml"
  spawn_timeout_ms: 5000
  validation_timeout_ms: 30000

coordination_service:
  base_url: "http://coordination-service:8080"
  timeout_ms: 5000
  retry_attempts: 3
  retry_delay_ms: 1000

logging:
  level: INFO
  destination: "./logs/validation-service.log"
  log_requests: true
  log_rule_performance: true

monitoring:
  enabled: true
  rule_performance_threshold_ms: 100
  alert_on_threshold_exceeded: true
  metrics_export_interval_ms: 60000
```

### REST API

#### Inline Validation

**Request:**
```http
POST /api/v1/validate
Content-Type: application/json

{
  "entity_type": "loan",
  "entity_data": {
    "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
    "id": "LOAN-12345",
    "amount": 500000,
    "currency": "USD",
    "facility_id": "FAC-789",
    "maturity_date": "2028-12-31",
    ...
  }
}
```

**Response:**
```json
{
  "entity_type": "loan",
  "entity_id": "LOAN-12345",
  "timestamp": "2026-02-02T10:30:00Z",
  "mode": "inline",
  "results": [
    {
      "rule_id": "rule_001",
      "description": "Loan amount must not exceed facility limit",
      "status": "PASS",
      "message": "",
      "execution_time_ms": 15,
      "children": [
        {
          "rule_id": "rule_042",
          "description": "Facility utilization must be below 95%",
          "status": "PASS",
          "message": "",
          "execution_time_ms": 8,
          "children": []
        }
      ]
    },
    {
      "rule_id": "rule_055",
      "description": "Currency must match facility currency",
      "status": "FAIL",
      "message": "Loan currency USD does not match facility currency EUR",
      "execution_time_ms": 5,
      "children": []
    }
  ],
  "summary": {
    "total_rules": 10,
    "passed": 8,
    "failed": 1,
    "not_run": 1,
    "total_time_ms": 245
  }
}
```

#### Batch Validation

**Inline Batch (POST /api/v1/batch):**

Validates multiple entities with inline data. Supports mixed entity types and flexible output modes.

**Request:**
```http
POST /api/v1/batch
Content-Type: application/json

{
  "entities": [
    {
      "entity_type": "loan",
      "entity_data": {
        "$schema": "file://../models/loan.schema.v1.0.0.json",
        "loan_number": "LN-001",
        ...
      }
    },
    {
      "entity_type": "loan",
      "entity_data": {
        "$schema": "file://../models/loan.schema.v1.0.0.json",
        "loan_number": "LN-002",
        ...
      }
    }
  ],
  "id_fields": {
    "file://../models/loan.schema.v1.0.0.json": "loan_number"
  },
  "ruleset_name": "quick",
  "output_mode": "response"  // or "file"
}
```

**Response (output_mode="response"):**
```json
{
  "batch_id": "BATCH-2026-02-12-001",
  "timestamp": "2026-02-12T10:30:00Z",
  "mode": "batch",
  "entity_count": 2,
  "results": [
    {
      "entity_type": "loan",
      "entity_id": "LN-001",
      "schema": "file://../models/loan.schema.v1.0.0.json",
      "status": "completed",
      "results": [...],
      "summary": {
        "total_rules": 2,
        "passed": 2,
        "failed": 0,
        "not_run": 0
      }
    },
    ...
  ],
  "overall_summary": {
    "total_entities": 2,
    "completed": 2,
    "errors": 0,
    "entities_with_failures": 0
  }
}
```

**File-Based Batch (POST /api/v1/batch-file):**

Loads entities from a file URI (file://, http://, https://). All entities must be of the same type.

**Request:**
```http
POST /api/v1/batch-file
Content-Type: application/json

{
  "file_uri": "file:./test/test-data/loans.json",
  "entity_types": {
    "file://../../models/loan.schema.v1.0.0.json": "loan"
  },
  "id_fields": {
    "file://../../models/loan.schema.v1.0.0.json": "loan_number"
  },
  "ruleset_name": "thorough",
  "output_mode": "file",
  "output_path": "test/results/validation-results.json"
}
```

**Response (output_mode="file"):**
```json
{
  "batch_id": "BATCH-2026-02-12-002",
  "status": "completed",
  "file_uri": "file:./test/test-data/loans.json",
  "output_path": "test/results/validation-results.json",
  "entity_count": 2,
  "message": "Results written to file"
}
```

**Key Features:**
- **Mixed Entity Types**: `/api/v1/batch` supports different entity types in one request
- **ID Field Mapping**: `id_fields` maps each schema URL to its ID field for correlation
- **Schema Validation**: Pre-validates that all schemas in batch have corresponding `id_fields` entries
- **Flexible Output**: Both endpoints support `output_mode` ("response" or "file")
- **File URIs**: `/api/v1/batch-file` supports file://, http://, and https:// protocols
- **Path Normalization**: Relative file:// URIs automatically converted to absolute paths for Python compatibility

#### File Path Handling and Containerization

**Relative Path Support:**

The service supports relative file:// URIs for container compatibility. All file paths are relative to the working directory (`jvm-service/`).

**Path Formats:**
- Schema URLs in entity data: `file://../models/loan.schema.v1.0.0.json`
- File URIs for batch-file: `file:./test/test-data/loans.json`
- HTTP/HTTPS URIs: `https://example.com/data.json`

**Automatic Path Normalization:**

Python's `urllib.request.urlopen()` cannot properly resolve relative file:// URIs (treats `file://../models/` as `/models/` from root). The JVM service automatically normalizes relative URIs to absolute paths before passing to Python.

**Implementation** (`src/validation_service/utils/file_io.clj`):
```clojure
(defn normalize-file-uri
  "Convert relative file:// URIs to absolute paths.

  Examples:
    file://../models/schema.json → file:///Users/jude/.../models/schema.json
    file:./test/data.json → file:///Users/jude/.../jvm-service/test/data.json
    http://example.com/data.json → http://example.com/data.json (unchanged)"
  [uri]
  (if (and uri (.startsWith uri "file:"))
    (let [is-relative? (or (.startsWith uri "file://..")
                         (.startsWith uri "file:."))]
      (if is-relative?
        ;; Resolve to absolute path using current working directory
        (let [path-str (remove-file-prefix uri)
              absolute-file (-> path-str io/file .getCanonicalFile)
              absolute-path (.getAbsolutePath absolute-file)]
          (str "file://" absolute-path))
        uri))
    uri))
```

**Workflow Integration:**

In `execute-validation` workflow:
1. Extract schema URL from `entity_data["$schema"]`
2. Normalize schema URL using `normalize-file-uri`
3. Update entity_data with normalized schema URL
4. Pass normalized URL to Python runner

**Container Directory Structure:**
```
/app/
├── models/              # At ../models from jvm-service/
│   └── loan.schema.v1.0.0.json
└── jvm-service/         # WORKDIR
    ├── test/
    │   └── test-data/   # At ./test/test-data from jvm-service/
    └── validation-service.jar
```

**Benefits:**
- Container-ready: Works in Docker/Podman without filesystem-specific paths
- Portable: Same relative paths work across different environments
- Python-compatible: Normalized absolute paths work with urllib
- Tested: All test suites pass with relative paths and schema validation working

### Validation Workflow

#### Inline Mode Flow

**JVM Inline Mode** = Real-time validation with "quick" rule set

```
1. Client → POST /api/v1/validate
2. JVM validates request
3. JVM uses persistent Python runner pod (created at service startup)
4. JVM → Python: get_required_data(entity_type, schema_url, ruleset_name="quick")
   - JVM decides to use "quick" rule set for inline mode (real-time, minimal checks)
   - schema_url extracted from entity_data['$schema'], used to determine version-specific rules
5. Python:
   - Loads config
   - Identifies rules for schema_url in "quick_rules" section (falls back to entity_type for backward compatibility)
   - Loads rule classes from file system
   - Calls required_data() on each rule
   - Aggregates and deduplicates
   - Returns: ["parent", "all_siblings", "client_reference_data"]
   - Note: "schema" is NOT a vocabulary term - schemas are in entity data via $schema field
6. JVM calls Coordination Service:
   - GET /api/data/parent/{entity_id}
   - GET /api/data/siblings/{entity_id}
   - GET /api/data/client/{client_id}
   - Schemas are loaded from local models/ files, NOT from coordination service
7. JVM aggregates fetched data into required_data dict
8. JVM → Python: validate(entity_type, entity_data, ruleset_name="quick", required_data)
9. Python:
   - Loads config and rules from "quick_rules" section (same as step 5)
   - Executes rules in hierarchical order:
     * Call set_required_data() with relevant data subset
     * Call run()
     * Capture status, message, timing
     * If PASS and has children, execute children
     * If FAIL or NORUN, skip children (mark as NORUN)
   - Returns hierarchical results
10. JVM receives results
11. JVM logs results to centralized log
12. JVM monitors rule performance (alerts if threshold exceeded)
13. JVM terminates Python runner process
14. JVM → Client: Return results
```

#### Batch Mode Flow

**JVM Batch Mode** = Background validation with "thorough" rule set

```
1. Client → POST /api/v1/validate/batch with entity list
2. JVM parses and validates request
3. JVM spawns Python runner pod (long-running process)
4. For each entity in batch:
   a. Execute same two-phase flow as inline mode BUT with ruleset_name="thorough"
   b. JVM passes "thorough" rule set for comprehensive validation
   c. Python runner loads more extensive rule set from "thorough_rules" config section
   d. Collect results
5. JVM terminates Python runner pod
6. JVM aggregates all entity results
7. JVM computes overall summary statistics
8. JVM logs batch results
9. JVM → Client: Return batch results
```

**Note:** A single pod instance is reused for all entities in the batch:
- Pods are long-running processes that handle multiple requests sequentially
- Avoids startup/shutdown overhead for each entity
- Maintains process isolation at the batch level
- Simplifies resource management (one process per batch, not per entity)
- Future enhancement: Pod pooling for parallel batch processing

### Performance Monitoring

The JVM service tracks and logs:

**Per-rule metrics:**
- Execution time (from Python runner timing data)
- Success rate (PASS/FAIL/NORUN distribution)
- Error patterns (common failure messages)

**Per-validation metrics:**
- Total validation time
- Python runner spawn overhead
- Coordination service call latency
- Number of rules executed

**Alerting:**
- Rule exceeds performance threshold (configured in config.yaml)
- Coordination service timeout/failures
- Python runner spawn failures
- Abnormal error rates

**Storage:**
- Metrics exported to time-series database (Prometheus, InfluxDB, etc.)
- Enables dashboards, trending, and historical analysis

## Python Rule Runner

### Technology Stack

- Python 3.10+
- bencodepy library for pod protocol (installed via `pip install bencodepy`)
- PyYAML for configuration
- jsonschema library for validating entity data against JSON Schema (POC phase)
- Standard library (importlib for dynamic loading)

### Directory Structure

```
python-runner/
├── runner.py                # Main entry point
├── config.yaml              # Rule configuration
├── validation_engine.py     # Core validation business logic
├── rule_loader.py           # Dynamic rule discovery and loading
├── rule_executor.py         # Rule execution engine
├── rule_test_helper.py      # Simple testing framework for rules
├── cache.py                 # Simple caching for entity/required data
├── requirements.txt         # Python dependencies
├── entity_helpers/          # Entity helper classes (wrappers for data model access)
│   ├── __init__.py          # Exports Loan, Facility, Deal, create_entity_helper
│   ├── base.py              # Shared base class and utilities (optional)
│   ├── loan_v1.py              # Loan helper class
│   ├── facility.py          # Facility helper class
│   └── deal.py              # Deal helper class
├── transport/               # Transport abstraction layer
│   ├── __init__.py
│   ├── base.py             # Abstract TransportHandler interface
│   ├── pods_transport.py   # Babashka pods implementation
│   └── grpc_transport.py   # gRPC implementation (future)
└── rules/                   # Master rules directory
    ├── loan/
    │   ├── rule_001_v1.py
    │   ├── rule_001_v2.py   # Updated version of rule_001
    │   ├── rule_042_v1.py
    │   ├── rule_055_v1.py
    │   ├── rule_055_v1_test.py  # Test for rule_055_v1
    │   └── rule_066_v1.py
    ├── facility/
    │   ├── rule_003_v1.py
    │   ├── rule_017_v1.py
    │   └── rule_018_v1.py
    └── deal/
        └── rule_010_v1.py
```

### Configuration

```yaml
# config.yaml - Python Runner Rule Set Configuration
#
# Note: The Python runner is rule-set agnostic. The JVM service has inline/batch
# modes for orchestration (when to call validation), and separately passes a
# ruleset_name to specify which rules to execute. These are independent concerns.
#
# JVM inline mode might use "quick_rules" (real-time, essential checks)
# JVM batch mode might use "thorough_rules" (background, comprehensive checks)
# But the JVM service controls this mapping, not the Python runner.

master_rules_directory: "./rules"

# Quick rule set - typically used for real-time validation
quick_rules:
  loan:
    - rule_id: rule_001_v2   # Using version 2 (updated rule)
      children:
        - rule_id: rule_042_v1
    - rule_id: rule_055_v1

  facility:
    - rule_id: rule_003_v1
      children:
        - rule_id: rule_017_v1
        - rule_id: rule_018_v1
          children:
            - rule_id: rule_019_v1

  deal:
    - rule_id: rule_010_v1

# Thorough rule set - typically used for batch/background validation
thorough_rules:
  loan:
    - rule_id: rule_001_v2   # Using version 2 (updated rule)
      children:
        - rule_id: rule_042_v1
        - rule_id: rule_066_v1  # Additional comprehensive check
    - rule_id: rule_055_v1
    - rule_id: rule_070_v1      # More comprehensive checks
    - rule_id: rule_071_v1

  facility:
    - rule_id: rule_003_v1
      children:
        - rule_id: rule_017_v1
        - rule_id: rule_018_v1
          children:
            - rule_id: rule_019_v1
    - rule_id: rule_025_v1      # Batch-only check

  deal:
    - rule_id: rule_010_v1
    - rule_id: rule_011_v1      # Batch-only check
```

**Configuration Notes:**
- Hierarchical structure: Child rules only execute if parent rule status is PASS
- Rule reuse: Same rule (e.g., rule_001) can appear in both inline and batch configs
- Flexibility: Easy to add/remove rules without code changes
- Arbitrary nesting: Supports multiple levels of rule hierarchy

### Entity Helper Classes

To decouple validation rules from the underlying data model structure, the Python runner provides typed helper classes for each entity type. Rules interact with these helpers rather than accessing raw JSON/dict data directly.

**Purpose:**
- Provide stable, version-independent interface to entity data
- Isolate rules from model structure changes (field renames, nesting changes)
- Enable model evolution without breaking existing rules
- Improve code readability and maintainability

**Helper Class Structure:**

```python
# entity_helpers/loan_v1.py

from typing import Optional, Any
from datetime import date

class LoanV1:
    """Helper class providing stable interface to loan data"""

    def __init__(self, data: dict):
        self._data = data

    @property
    def id(self) -> str:
        """Loan identifier"""
        return self._data.get("id", "")

    @property
    def amount(self) -> float:
        """Loan principal amount"""
        return self._data.get("amount", 0.0)

    @property
    def currency(self) -> str:
        """Loan currency code (e.g., USD, EUR)"""
        return self._data.get("currency", "")

    @property
    def facility_id(self) -> str:
        """Parent facility identifier"""
        return self._data.get("facility_id", "")

    @property
    def maturity_date(self) -> Optional[date]:
        """Loan maturity date"""
        date_str = self._data.get("maturity_date")
        if date_str:
            return date.fromisoformat(date_str)
        return None

    @property
    def interest_rate(self) -> Optional[float]:
        """Annual interest rate as decimal (e.g., 0.05 for 5%)"""
        return self._data.get("interest_rate")

    # Computed properties can be added
    @property
    def is_overdue(self) -> bool:
        """Check if loan is past maturity"""
        if self.maturity_date:
            from datetime import date
            return date.today() > self.maturity_date
        return False


class Facility:
    """Helper class providing stable interface to facility data"""

    def __init__(self, data: dict):
        self._data = data

    @property
    def id(self) -> str:
        return self._data.get("id", "")

    @property
    def limit(self) -> float:
        """Facility credit limit"""
        return self._data.get("limit", 0.0)

    @property
    def currency(self) -> str:
        return self._data.get("currency", "")

    @property
    def deal_id(self) -> str:
        """Parent deal identifier"""
        return self._data.get("deal_id", "")

    @property
    def maturity_date(self) -> Optional[date]:
        date_str = self._data.get("maturity_date")
        if date_str:
            return date.fromisoformat(date_str)
        return None

    @property
    def utilization(self) -> float:
        """Current facility utilization amount"""
        return self._data.get("utilization", 0.0)

    @property
    def utilization_percentage(self) -> float:
        """Computed: utilization as percentage of limit"""
        if self.limit > 0:
            return (self.utilization / self.limit) * 100
        return 0.0


class Deal:
    """Helper class providing stable interface to deal data"""

    def __init__(self, data: dict):
        self._data = data

    @property
    def id(self) -> str:
        return self._data.get("id", "")

    @property
    def client_id(self) -> str:
        return self._data.get("client_id", "")

    @property
    def origination_date(self) -> Optional[date]:
        date_str = self._data.get("origination_date")
        if date_str:
            return date.fromisoformat(date_str)
        return None

    @property
    def deal_type(self) -> str:
        return self._data.get("deal_type", "")

    @property
    def status(self) -> str:
        return self._data.get("status", "")
```

**Helper Factory:**

```python
# entity_helpers/__init__.py (factory function)

def create_entity_helper(entity_type: str, entity_data: dict):
    """Factory function to create appropriate helper based on entity type"""
    helpers = {
        "loan": Loan,
        "facility": Facility,
        "deal": Deal
    }

    helper_class = helpers.get(entity_type)
    if not helper_class:
        raise ValueError(f"Unknown entity type: {entity_type}")

    return helper_class(entity_data)
```

**Integration with Rule Executor:**

The rule executor automatically wraps entity data in helper classes before passing to rules:

```python
# rule_executor.py (modified)

from entity_helpers import create_entity_helper

class RuleExecutor:
    def __init__(self, rules, entity_type, entity_data, required_data):
        self.rules = {r.get_id(): r for r in rules}
        self.entity_type = entity_type
        self.entity_data = entity_data
        self.required_data = required_data

        # Create entity helper
        self.entity_helper = create_entity_helper(entity_type, entity_data)

    def _execute_rule(self, config):
        """Execute a single rule and its children."""
        rule_id = config["rule_id"]
        rule = self.rules.get(rule_id)

        if not rule:
            # ... handle missing rule ...
            pass

        # Provide entity helper to rule (not raw data!)
        rule.entity = self.entity_helper

        # Provide required data to rule
        rule_required = rule.required_data()
        rule_data = {k: self.required_data.get(k) for k in rule_required}
        rule.set_required_data(rule_data)

        # Execute rule
        status, message = rule.run()
        # ... rest of execution logic ...
```

**Model Evolution Example:**

Initial model structure:
```json
{
  "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
  "id": "LOAN-123",
  "amount": 500000,
  "currency": "USD"
}
```

Rule accesses via helper:
```python
loan_amount = self.entity.amount  # Works
```

Model restructured later:
```json
{
  "$schema": "https://bank.example.com/schemas/loan/v2.0.0",
  "id": "LOAN-123",
  "financial": {
    "principal_amount": 500000,
    "currency_code": "USD"
  }
}
```

Only helper updated:
```python
class LoanV1:
    @property
    def amount(self) -> float:
        # Updated to handle new structure
        return self._data.get("financial", {}).get("principal_amount", 0.0)

    @property
    def currency(self) -> str:
        return self._data.get("financial", {}).get("currency_code", "")
```

**Rules remain unchanged** - they still call `self.entity.amount` and get the correct value!

**Benefits:**
- **Isolation:** 100+ existing rules unaffected by model restructure
- **Maintenance:** Single point of change (helper class) vs. many rules
- **Versioning:** Helpers can support multiple model versions during transitions
- **Testing:** Helper classes can be unit tested independently
- **Documentation:** Helper properties serve as data dictionary

#### Field Access Tracking

**Purpose:** Track which data model fields are actually accessed by rules to support model change impact analysis.

Entity helper classes include instrumentation to record field access, enabling analysis of rule dependencies on specific data fields.

**Implementation:**

```python
# entity_helpers/loan_v1.py (enhanced with tracking)

from typing import Optional, Any, Set
from datetime import date

class LoanV1:
    """Helper class with field access tracking"""

    def __init__(self, data: dict, track_access: bool = False):
        self._data = data
        self._track_access = track_access
        self._accessed_fields: Set[str] = set()

    def _record_access(self, field_name: str):
        """Record that a field was accessed"""
        if self._track_access:
            self._accessed_fields.add(field_name)

    def get_accessed_fields(self) -> Set[str]:
        """Return set of fields accessed during rule execution"""
        return self._accessed_fields

    @property
    def amount(self) -> float:
        """Loan principal amount"""
        self._record_access("amount")
        return self._data.get("amount", 0.0)

    @property
    def currency(self) -> str:
        """Loan currency code"""
        self._record_access("currency")
        return self._data.get("currency", "")

    @property
    def maturity_date(self) -> Optional[date]:
        """Loan maturity date"""
        self._record_access("maturity_date")
        date_str = self._data.get("maturity_date")
        if date_str:
            return date.fromisoformat(date_str)
        return None

    # ... other properties similarly instrumented
```

**Usage in Rule Executor:**

```python
# rule_executor.py (modified for tracking)

from entity_helpers import create_entity_helper

class RuleExecutor:
    def __init__(self, rules, entity_type, entity_data, required_data,
                 track_field_access=False):
        self.rules = {r.get_id(): r for r in rules}
        self.entity_type = entity_type
        self.entity_data = entity_data
        self.required_data = required_data
        self.track_field_access = track_field_access

        # Create entity helper with tracking enabled
        self.entity_helper = create_entity_helper(
            entity_type,
            entity_data,
            track_access=track_field_access
        )

    def get_field_dependencies(self, rule_id: str) -> Set[str]:
        """Get fields accessed by a specific rule"""
        rule = self.rules.get(rule_id)
        if not rule:
            return set()

        # Reset tracking
        self.entity_helper._accessed_fields.clear()

        # Execute rule
        rule.entity = self.entity_helper
        rule.run()

        # Return accessed fields
        return self.entity_helper.get_accessed_fields()
```

**Dependency Analysis Script:**

`scripts/catalog_rule_dependencies.sh`:

```bash
#!/bin/bash
# Catalog which data fields each rule depends on

set -e

PYTHON_RUNNER_DIR="python-runner"
OUTPUT_FILE="docs/rule_field_dependencies.json"

echo "Analyzing rule field dependencies..."
echo "This may take a few minutes..."

cd "$PYTHON_RUNNER_DIR"

python3 << 'EOF'
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from validation_engine import ValidationEngine
from entity_helpers import Loan, Facility, Deal
from rule_loader import RuleLoader
from rule_executor import RuleExecutor
import yaml

# Load configuration
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Sample test data for each entity type
test_data = {
    "loan": {
        "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
        "id": "LOAN-TEST",
        "amount": 500000,
        "currency": "USD",
        "facility_id": "FAC-TEST",
        "maturity_date": "2028-12-31",
        "interest_rate": 0.05
    },
    "facility": {
        "$schema": "https://bank.example.com/schemas/facility/v1.0.0",
        "id": "FAC-TEST",
        "limit": 1000000,
        "currency": "USD",
        "deal_id": "DEAL-TEST",
        "maturity_date": "2029-12-31",
        "utilization": 500000
    },
    "deal": {
        "$schema": "https://bank.example.com/schemas/deal/v1.0.0",
        "id": "DEAL-TEST",
        "client_id": "CLIENT-TEST",
        "origination_date": "2024-01-01",
        "deal_type": "revolving",
        "status": "active"
    }
}

# Sample required data (minimal for testing)
required_data_samples = {
    "parent": test_data["facility"],
    "all_children": [],
    "all_siblings": []
}

def analyze_rules(config, mode):
    """Analyze all rules in a given mode"""
    results = {}

    for entity_type in ["loan", "facility", "deal"]:
        mode_key = f"{mode}_rules"
        rule_configs = config.get(mode_key, {}).get(entity_type, [])

        if not rule_configs:
            continue

        loader = RuleLoader(config)
        rules = loader.load_rules(rule_configs)

        # Execute each rule with field tracking enabled
        executor = RuleExecutor(
            rules=rules,
            entity_type=entity_type,
            entity_data=test_data[entity_type],
            required_data=required_data_samples,
            track_field_access=True
        )

        for rule_config in rule_configs:
            rule_id = rule_config["rule_id"]

            try:
                # Get field dependencies
                fields = executor.get_field_dependencies(rule_id)

                rule = [r for r in rules if r.get_id() == rule_id][0]

                results[rule_id] = {
                    "entity_type": entity_type,
                    "mode": mode,
                    "description": rule.description(),
                    "accessed_fields": sorted(list(fields)),
                    "required_data": rule.required_data()
                }

                print(f"  {rule_id}: {len(fields)} fields accessed")

            except Exception as e:
                print(f"  {rule_id}: ERROR - {str(e)}", file=sys.stderr)
                results[rule_id] = {
                    "error": str(e)
                }

    return results

# Analyze both modes
print("\nAnalyzing inline rules...")
inline_results = analyze_rules(config, "inline")

print("\nAnalyzing batch rules...")
batch_results = analyze_rules(config, "batch")

# Combine results
all_results = {
    "inline": inline_results,
    "batch": batch_results,
    "generated_at": str(datetime.now())
}

# Write to JSON file
output_path = Path("../docs/rule_field_dependencies.json")
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w") as f:
    json.dump(all_results, f, indent=2)

print(f"\n✓ Dependency analysis complete!")
print(f"Results written to: {output_path}")

# Generate summary report
print("\n=== Field Dependency Summary ===")
all_fields = set()
for mode_results in [inline_results, batch_results]:
    for rule_id, rule_info in mode_results.items():
        if "accessed_fields" in rule_info:
            all_fields.update(rule_info["accessed_fields"])

print(f"Total unique fields accessed: {len(all_fields)}")
print(f"Fields: {sorted(all_fields)}")

EOF

echo ""
echo "✓ Analysis complete!"
echo "Results: $OUTPUT_FILE"
```

**Example Output** (`docs/rule_field_dependencies.json`):

```json
{
  "inline": {
    "rule_001_v2": {
      "entity_type": "loan",
      "mode": "inline",
      "description": "Loan amount must not exceed facility limit",
      "accessed_fields": ["amount"],
      "required_data": ["parent"]
    },
    "rule_055_v1": {
      "entity_type": "loan",
      "mode": "inline",
      "description": "Currency must match facility currency",
      "accessed_fields": ["currency"],
      "required_data": ["parent"]
    }
  },
  "batch": {
    "rule_001_v2": {
      "entity_type": "loan",
      "mode": "batch",
      "accessed_fields": ["amount", "facility_id"],
      "required_data": ["parent"]
    }
  },
  "generated_at": "2026-02-02T15:30:00"
}
```

**Use Cases:**

1. **Model Change Impact Analysis:**
   ```bash
   # Before removing "interest_rate" field
   ./scripts/catalog_rule_dependencies.sh
   grep "interest_rate" docs/rule_field_dependencies.json
   # Shows which rules would be affected
   ```

2. **Model Version Planning:**
   ```bash
   # Check which rules use "amount" vs "principal_amount"
   grep "amount" docs/rule_field_dependencies.json
   # Plan migration strategy
   ```

3. **Rule Documentation:**
   - Automatically document what data each rule actually uses
   - Verify rule required_data declarations are complete
   - Identify unused fields in data model

4. **Regression Testing:**
   - Run before and after helper class changes
   - Ensure field access patterns haven't changed unexpectedly
   - Verify backward compatibility

**Benefits:**
- **Visibility:** Know exactly which rules depend on which fields
- **Safe Evolution:** Remove fields confidently (no hidden dependencies)
- **Impact Analysis:** Quantify scope of model changes
- **Documentation:** Auto-generated field usage documentation
- **Testing:** Verify helper class changes don't break field access

This introspection capability transforms model evolution from risky to manageable by providing clear visibility into rule-field dependencies.

### Rule Class Interface

Each rule is a Python class following this interface:

```python
# Example: rules/loan/rule_001_v1.py

from rules.base import ValidationRule
from entity_helpers import Facility

class Rule(ValidationRule):
    """
    Loan amount must not exceed facility limit.

    All rules use the standard class name 'Rule'.
    The rule ID is derived from the filename (rule_001_v1.py → rule_001_v1).
    """

    def validates(self) -> str:
        """Return entity type this rule validates."""
        return "loan"

    def required_data(self) -> list[str]:
        """
        Return list of required data vocabulary terms.

        Returns terms from fixed vocabulary:
        - Hierarchical: parent, all_children, all_siblings, parent's_parent
        - Related: related_parties, parent's_legal_document, client_reference_data
        """
        return ["parent"]  # Need parent facility data

    def description(self) -> str:
        """Return plain English description of rule."""
        return "Loan amount must not exceed facility limit"

    def set_required_data(self, data: dict) -> None:
        """
        Receive required data before execution.

        Args:
            data: Dict with vocabulary terms as keys
                  e.g., {"parent": {...}, "all_siblings": [...]}
        """
        parent_data = data.get("parent")
        # Wrap parent facility data in helper for stable interface
        self.parent_facility = Facility(parent_data) if parent_data else None

    def run(self) -> tuple[str, str]:
        """
        Execute validation rule.

        Note: self.entity is a Loan helper instance (provided by rule executor)

        Returns:
            Tuple of (status, message)
            status: "PASS" | "FAIL" | "NORUN"
            message: Error description (empty string for PASS)
        """
        if not self.parent_facility:
            return ("NORUN", "Parent facility data not available")

        # Use entity helpers instead of raw dict access
        loan_amount = self.entity.amount
        facility_limit = self.parent_facility.limit

        if loan_amount > facility_limit:
            return ("FAIL",
                    f"Loan amount {loan_amount} exceeds facility limit {facility_limit}")

        return ("PASS", "")
```

**Rule Naming Convention:**
- File: `rule_<id>_v<version>.py` (e.g., `rule_001_v1.py`, `rule_001_v2.py`)
- Class: Always `Rule` (standard name for all rules)
- Rule ID: Automatically derived from filename (e.g., `rule_001_v1.py` → `rule_001_v1`)
- Class docstring: Brief description of rule purpose
- Version starts at v1, increments with each update

**Rule Versioning Strategy:**

Rules are versioned to enable safe updates and rollbacks:

```
rules/loan/
  rule_001_v1.py    # Original version
  rule_001_v2.py    # Updated version (new logic)
  rule_042_v1.py
```

Configuration specifies which version to use:
```yaml
inline_rules:
  loan:
    - rule_id: rule_001_v2      # Use version 2
      children:
        - rule_id: rule_042_v1  # Use version 1
```

Benefits:
- Safe updates: Deploy new version, test in staging, promote to production
- Easy rollback: Change config back to v1 if v2 has issues
- A/B testing: Different configs can use different versions
- Audit trail: Clear history of rule changes in version control

When updating a rule:
1. Copy existing file (e.g., `rule_001_v1.py` → `rule_001_v2.py`)
2. Modify logic in new version (class name remains `Rule`)
3. Test new version (see Rule Testing Framework below)
4. Update config to reference new version (`rule_001_v2`)
5. Keep old version for rollback capability

Note: All rule classes use the standard name `Rule`. The rule ID is derived from the filename, so no class name changes are needed when versioning.

### Rule Testing Framework

A simple testing framework enables rule authors to verify rule logic before deployment.

**Test File Convention:**
- Test file: `rule_<id>_v<version>_test.py` (e.g., `rule_055_v1_test.py`)
- Located in same directory as rule being tested
- Uses standard Python `assert` statements

**Simple Test Helper:**

```python
# rule_test_helper.py

from entity_helpers import create_entity_helper
from typing import Any, Dict, Type

class RuleTestHelper:
    """Simple helper for testing validation rules"""

    @staticmethod
    def test_rule(
        rule_class: Type,
        entity_type: str,
        entity_data: Dict[str, Any],
        required_data: Dict[str, Any],
        expected_status: str,
        expected_message: str = None
    ):
        """
        Test a rule with given inputs and verify expected output.

        Args:
            rule_class: The rule class to test
            entity_type: Type of entity ("loan", "facility", "deal")
            entity_data: Entity data as dict
            required_data: Additional required data as dict
            expected_status: Expected status ("PASS", "FAIL", "NORUN")
            expected_message: Expected message (if None, only checks status)
        """
        # Create rule instance
        rule = rule_class()

        # Provide entity helper
        rule.entity = create_entity_helper(entity_type, entity_data)

        # Provide required data
        rule.set_required_data(required_data)

        # Execute rule
        status, message = rule.run()

        # Verify results
        assert status == expected_status, \
            f"Expected status {expected_status}, got {status}"

        if expected_message is not None:
            assert message == expected_message, \
                f"Expected message '{expected_message}', got '{message}'"

        print(f"✓ Test passed: {rule.get_id()} - {rule.description()}")
```

**Example Test File:**

```python
# rules/loan/rule_055_v1_test.py

import sys
sys.path.append('../..')  # Add parent dirs to path

from rule_055_v1 import Rule
from rule_test_helper import RuleTestHelper

def test_currency_match_pass():
    """Test that matching currencies pass validation"""
    RuleTestHelper.test_rule(
        rule_class=Rule,
        rule_id="rule_055_v1",
        entity_type="loan",
        entity_data={
            "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
            "id": "LOAN-123",
            "amount": 500000,
            "currency": "USD",
            "facility_id": "FAC-789"
        },
        required_data={
            "parent": {
                "$schema": "https://bank.example.com/schemas/facility/v1.0.0",
                "id": "FAC-789",
                "limit": 1000000,
                "currency": "USD"
            }
        },
        expected_status="PASS",
        expected_message=""
    )

def test_currency_mismatch_fail():
    """Test that mismatched currencies fail validation"""
    RuleTestHelper.test_rule(
        rule_class=Rule,
        entity_type="loan",
        entity_data={
            "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
            "id": "LOAN-123",
            "amount": 500000,
            "currency": "USD",
            "facility_id": "FAC-789"
        },
        required_data={
            "parent": {
                "$schema": "https://bank.example.com/schemas/facility/v1.0.0",
                "id": "FAC-789",
                "limit": 1000000,
                "currency": "EUR"
            }
        },
        expected_status="FAIL",
        expected_message="Loan currency USD does not match facility currency EUR"
    )

def test_missing_parent_norun():
    """Test that missing parent data returns NORUN"""
    RuleTestHelper.test_rule(
        rule_class=Rule,
        entity_type="loan",
        entity_data={
            "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
            "id": "LOAN-123",
            "amount": 500000,
            "currency": "USD"
        },
        required_data={},
        expected_status="NORUN",
        expected_message="Parent facility data not available"
    )

if __name__ == "__main__":
    # Run all tests
    test_currency_match_pass()
    test_currency_mismatch_fail()
    test_missing_parent_norun()
    print("\n✓ All tests passed!")
```

**Running Tests:**

```bash
# Run single rule test
cd python-runner/rules/loan
python rule_055_v1_test.py

# Run all tests in a directory
python -m pytest loan/

# Run all tests in project
python -m pytest rules/
```

**Benefits:**
- Simple: No complex test framework dependencies
- Fast: Quick feedback for rule authors
- Repeatable: Tests serve as documentation and regression suite
- Safe: Verify rule changes before deployment

**POC Testing Strategy:**
- Rule authors write at least 3 test cases: PASS, FAIL, NORUN scenarios
- Tests run locally before committing rule changes
- Optional: CI/CD runs all rule tests on pull requests (future enhancement)

### Required Data Vocabulary

Rules reference additional data using a **fixed, controlled vocabulary**. The Python runner validates that rules only use approved terms.

**Hierarchical Relationships:**
- `parent` - Immediate parent entity
- `all_children` - All child entities
- `all_siblings` - All sibling entities (same parent)
- `parent's_parent` - Grandparent entity
- `first_child` - First child entity (if ordering exists)
- `last_child` - Last child entity

**Related Entities:**
- `related_parties` - Related party entities
- `parent's_legal_document` - Legal document associated with parent
- `client_reference_data` - Client master data
- `collateral_data` - Associated collateral information
- `historical_data` - Historical versions of entity

**Temporal:**
- `previous_version` - Previous version of this entity
- `all_versions` - All historical versions

**Schema Handling (RESOLVED):**
Schemas are NOT fetched as required data. Every entity contains a `$schema` field (e.g., `"$schema": "https://bank.example.com/schemas/loan/v1.0.0"`) that identifies its schema version. Schemas are stored in the local `models/` directory and loaded directly by rules when needed. The `$schema` URL is used to determine which version-specific rules apply to the entity.

Example rule using schema validation:
```python
from jsonschema import validate, ValidationError

class RuleSchemaValidation:
    def required_data(self) -> list[str]:
        return ["schema"]  # Request schema from JVM

    def set_required_data(self, data: dict) -> None:
        self.schema = data.get("schema")

    def run(self) -> tuple[str, str]:
        if not self.schema:
            return ("NORUN", "Schema not available")

        try:
            validate(instance=self.entity_data, schema=self.schema)
            return ("PASS", "")
        except ValidationError as e:
            return ("FAIL", f"Schema validation failed: {e.message}")
```

The vocabulary is extensible but changes require updates to both the Python runner's validation logic and the coordination service's data provisioning capabilities.

### Implementation with Transport Abstraction

The Python runner implementation separates transport concerns from validation business logic.

#### Core Validation Engine

```python
# validation_engine.py
import yaml
from rule_loader import RuleLoader
from rule_executor import RuleExecutor

class ValidationEngine:
    """Core validation business logic, independent of transport"""

    def __init__(self, config_path):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.rule_loader = RuleLoader(self.config)

    def get_required_data(self, entity_type, schema_url, mode):
        """
        Phase 1: Introspect rules and return required data.

        Returns list of vocabulary terms needed for validation.

        Args:
            schema_url: Used to determine which version-specific rules to load
        """
        # Load version-specific rules based on schema_url
        rule_configs = self._get_rules_for_mode(entity_type, mode, schema_url)
        rules = self.rule_loader.load_rules(rule_configs)

        # Collect all required_data from all rules
        required = set()
        for rule in rules:
            required.update(rule.required_data())

        return list(required)

    def validate(self, entity_type, entity_data, mode, required_data):
        """
        Phase 2: Execute rules and return hierarchical results.

        Returns structured results matching config hierarchy.
        """
        # Load rules
        rule_configs = self._get_rules_for_mode(entity_type, mode)
        rules = self.rule_loader.load_rules(rule_configs)

        # Execute with hierarchy
        executor = RuleExecutor(rules, entity_data, required_data)
        results = executor.execute_hierarchical(rule_configs)

        return results

    def _get_rules_for_mode(self, entity_type, mode):
        """Extract rule configs for given entity type and mode."""
        mode_key = f"{mode}_rules"
        return self.config.get(mode_key, {}).get(entity_type, [])
```

#### Transport Layer

```python
# transport/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class TransportHandler(ABC):
    """Abstract base class for transport layer"""

    @abstractmethod
    def start(self):
        """Initialize transport and start listening for requests"""
        pass

    @abstractmethod
    def send_response(self, request_id: str, result: Any):
        """Send successful response to client"""
        pass

    @abstractmethod
    def send_error(self, request_id: str, error: str):
        """Send error response to client"""
        pass

    @abstractmethod
    def receive_request(self) -> tuple[str, str, Dict[str, Any]]:
        """
        Receive next request from client.

        Returns:
            Tuple of (request_id, function_name, arguments_dict)
        """
        pass
```

```python
# transport/pods_transport.py
import sys
import bencode
from transport.base import TransportHandler
from typing import Any, Dict

class PodsTransportHandler(TransportHandler):
    """Babashka pods transport implementation using bencode over stdin/stdout"""

    def start(self):
        """Pods transport is ready as soon as process starts"""
        pass

    def send_response(self, request_id: str, result: Any):
        """Encode and send response via stdout"""
        response = {"id": request_id, "value": result}
        sys.stdout.buffer.write(bencode.encode(response))
        sys.stdout.buffer.flush()

    def send_error(self, request_id: str, error: str):
        """Encode and send error via stdout"""
        response = {"id": request_id, "error": error}
        sys.stdout.buffer.write(bencode.encode(response))
        sys.stdout.buffer.flush()

    def receive_request(self) -> tuple[str, str, Dict[str, Any]]:
        """Read and decode request from stdin"""
        msg = bencode.decode(sys.stdin.buffer)

        if msg.get("op") != "invoke":
            raise ValueError(f"Unsupported operation: {msg.get('op')}")

        return (
            msg.get("id"),
            msg.get("var"),
            msg.get("args", {})
        )
```

#### Main Entry Point

```python
# runner.py
import sys
from transport.pods_transport import PodsTransportHandler
from validation_engine import ValidationEngine

def main():
    """Main entry point with pluggable transport"""
    config_path = sys.argv[1] if len(sys.argv) > 1 else "./config.yaml"

    # Initialize components
    engine = ValidationEngine(config_path)
    transport = PodsTransportHandler()  # Pluggable: could be GrpcTransportHandler

    transport.start()

    # Main request loop
    while True:
        try:
            request_id, function_name, args = transport.receive_request()

            # Dispatch to validation engine
            if function_name == "get_required_data":
                result = engine.get_required_data(
                    args["entity_type"],
                    args["entity_data"],
                    args["mode"]
                )
            elif function_name == "validate":
                result = engine.validate(
                    args["entity_type"],
                    args["entity_data"],
                    args["mode"],
                    args["required_data"]
                )
            else:
                raise ValueError(f"Unknown function: {function_name}")

            transport.send_response(request_id, result)

        except Exception as e:
            transport.send_error(request_id, str(e))

if __name__ == "__main__":
    main()
```

**Key Design Points:**

1. **ValidationEngine** contains all business logic and has no knowledge of transport
2. **TransportHandler** abstraction allows swapping protocols without changing business logic
3. **runner.py** is thin glue code that connects transport to engine
4. Future gRPC implementation only requires implementing `GrpcTransportHandler`
5. Business logic can be unit tested without any transport dependencies

### Rule Execution Logic

```python
# rule_executor.py (simplified)

import time

class RuleExecutor:
    def __init__(self, rules, entity_data, required_data):
        self.rules = {r.get_id(): r for r in rules}
        self.entity_data = entity_data
        self.required_data = required_data

        # Simple cache for entity and required data
        self.cache = {
            "entity": entity_data,
            "required": required_data
        }

    def execute_hierarchical(self, rule_configs):
        """
        Execute rules respecting hierarchical dependencies.

        Args:
            rule_configs: List of rule config dicts with structure:
                [{"rule_id": "rule_001", "children": [...]}, ...]

        Returns:
            Hierarchical results structure matching config
        """
        results = []
        for config in rule_configs:
            result = self._execute_rule(config)
            results.append(result)
        return results

    def _execute_rule(self, config):
        """Execute a single rule and its children."""
        rule_id = config["rule_id"]
        rule = self.rules.get(rule_id)

        if not rule:
            return {
                "rule_id": rule_id,
                "status": "NORUN",
                "message": f"Rule {rule_id} not found",
                "execution_time_ms": 0,
                "children": []
            }

        # Provide required data to rule
        rule_required = rule.required_data()
        rule_data = {k: self.required_data.get(k) for k in rule_required}
        rule.set_required_data(rule_data)

        # Execute rule with timing
        start = time.time()
        status, message = rule.run()
        elapsed_ms = int((time.time() - start) * 1000)

        # Build result
        result = {
            "rule_id": rule_id,
            "description": rule.description(),
            "status": status,
            "message": message,
            "execution_time_ms": elapsed_ms,
            "children": []
        }

        # Execute children only if parent passed
        if status == "PASS" and "children" in config:
            for child_config in config["children"]:
                child_result = self._execute_rule(child_config)
                result["children"].append(child_result)
        elif status in ["FAIL", "NORUN"] and "children" in config:
            # Mark children as NORUN since parent didn't pass
            for child_config in config["children"]:
                result["children"].append(self._mark_skipped(child_config))

        return result

    def _mark_skipped(self, config):
        """Mark a rule and its children as skipped."""
        rule_id = config["rule_id"]
        rule = self.rules.get(rule_id)

        result = {
            "rule_id": rule_id,
            "description": rule.description() if rule else "",
            "status": "NORUN",
            "message": "Parent rule did not pass, rule skipped",
            "execution_time_ms": 0,
            "children": []
        }

        # Recursively mark children
        if "children" in config:
            for child_config in config["children"]:
                result["children"].append(self._mark_skipped(child_config))

        return result
```

### Caching Strategy

The Python runner implements simple in-memory caching for the duration of a validation job:

**What is cached:**
1. **Entity data**: The entity being validated (same for all rules)
2. **Required data**: Additional data fetched by JVM (reused across rules)
3. **Loaded rule instances**: Rule objects instantiated once

**Cache lifetime:**
- Single validation job only
- Cache cleared when runner process terminates
- No cross-request caching (each spawn is fresh)

**Implementation:**
Simple Python dict stored in RuleExecutor instance.

## Coordination Service Integration

### Service Contract

The coordination service provides additional data required by validation rules. It is an external service maintained separately.

**Assumed Interface (to be defined):**

```http
GET /api/data/parent/{entity_type}/{entity_id}
Returns: Parent entity data

GET /api/data/children/{entity_type}/{entity_id}
Returns: Array of child entity data

GET /api/data/siblings/{entity_type}/{entity_id}
Returns: Array of sibling entity data

GET /api/data/client/{client_id}
Returns: Client reference data

GET /api/data/related_parties/{entity_id}
Returns: Related party entities

... (one endpoint per vocabulary term)

Note: Schemas are stored in the models/ directory and loaded from local files. Schema URLs in entity data ($schema field) determine which version-specific rules apply. Schemas are NOT fetched from the coordination service.
```

**Response Format:**
```json
{
  "vocabulary_term": "parent",
  "entity_type": "facility",
  "entity_id": "FAC-789",
  "data": {
    "$schema": "https://bank.example.com/schemas/facility/v1.0.0",
    "id": "FAC-789",
    "limit": 1000000,
    "currency": "USD",
    ...
  }
}
```

### Error Handling

**Coordination service failures:**
- Timeout: JVM retries based on config (retry_attempts, retry_delay_ms)
- 404 Not Found: Treat as missing data, validation may return NORUN
- 500 Server Error: Log error, retry, return error to client if all retries fail

**Impact on validation:**
- If required data cannot be fetched, affected rules return NORUN
- Validation continues for rules that don't need the missing data
- Clear error messages indicate which data was unavailable

## Error Handling & Edge Cases

### Rule Execution Errors

**Exception during rule.run():**
- Catch exception in rule_executor
- Return status=NORUN with error message
- Log full stack trace for debugging
- Continue with remaining rules

**Missing required data:**
- Rule returns NORUN with message "Required data not available"
- Validation continues

**Rule loading failures:**
- Log error with rule_id and file path
- Skip rule (treat as NORUN in results)
- Don't fail entire validation

### Process Management

**Python runner spawn failure:**
- Log error with command and exit code
- Return HTTP 500 to client with clear error message
- Alert monitoring system

**Python runner timeout:**
- Kill process after timeout (configured in config.yaml)
- Return timeout error to client
- Log for investigation

**Python runner crash:**
- Detect via exit code
- Log stderr output
- Return error to client

### Data Validation

**Invalid entity_data:**
- Validate against expected schema (if defined)
- Return HTTP 400 with validation errors
- Don't spawn Python runner

**Invalid configuration:**
- Validate on service startup
- Fail fast if config is invalid
- Clear error messages about what's wrong

**Rule references non-existent rule:**
- Python runner logs error
- Rule marked as NORUN in results
- Validation continues

## Performance Considerations

### Performance Requirements

**Inline mode:**
- Target: Sub-second response time
- Typical: 10-20 rules per entity
- Budget: ~50ms per rule on average

**Batch mode:**
- Target: Process 1000 entities in reasonable time
- Parallel processing capability (future)

### Optimization Strategies

**Python runner:**
- **Single persistent pod** - Created once at service startup, not per request
- Eliminates pod spawn overhead for each validation
- Cache entity and required data during execution
- Load rule classes once at initialization
- Sequential execution (simpler, predictable)
- Reused across all inline and batch requests

**JVM service:**
- Parallel coordination service calls (fetch all required data concurrently)
- Connection pooling for coordination service
- Async batch processing (future)

**Coordination service:**
- Implement caching on coordination service side
- Batch data fetching APIs (future optimization)

### Monitoring & Alerting

**Key metrics:**
- Per-rule execution time (identify slow rules)
- Pod communication latency (bencode protocol overhead)
- Coordination service latency
- End-to-end validation time
- Batch processing throughput
- Error rates by rule and by service

**Alert conditions:**
- Rule exceeds performance threshold
- Validation timeout
- High error rate (>5% in 5 minutes)
- Coordination service degradation

## Deployment

Both POC and production phases use **Docker containerization** for packaging and deployment, ensuring consistent environments across development, staging, and production.

### POC Phase (Implemented)

**Packaging:**

The POC is packaged as a single Docker image using **multi-stage build** containing:
- Clojure service (JVM) - built to uberjar
- Python 3.10+ runtime
- Python runner code and dependencies
- JSON Schema models
- Validation rules

**Multi-Stage Dockerfile:**
```dockerfile
# ============ Builder Stage ============
FROM clojure:temurin-21-tools-deps-bookworm AS builder

WORKDIR /build/jvm-service
COPY jvm-service/deps.edn .
COPY jvm-service/build.clj .

# Download dependencies (cached layer)
RUN clojure -P -M:build

# Copy source and build uberjar
COPY jvm-service/src src/
COPY jvm-service/resources resources/
RUN clojure -T:build uber

# ============ Runtime Stage ============
FROM eclipse-temurin:21-jre-jammy

# Install Python 3 and dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy models directory (schemas)
COPY models/ models/

# Copy Python runner
COPY python-runner/ python-runner/
RUN pip3 install --no-cache-dir -r python-runner/requirements.txt

# Copy JVM service
COPY jvm-service/config.edn jvm-service/
COPY jvm-service/resources jvm-service/resources/
COPY --from=builder /build/jvm-service/target/validation-service-0.1.0-SNAPSHOT-standalone.jar jvm-service/validation-service.jar

# Set working directory (required for relative paths)
WORKDIR /app/jvm-service

EXPOSE 8080
ENV JAVA_OPTS="-Xmx512m -Xms256m"
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "java $JAVA_OPTS -jar validation-service.jar"]
```

**Container Directory Structure:**
```
/app/
├── models/                           # JSON schemas
│   └── loan.schema.v1.0.0.json
├── python-runner/                    # Python validation engine
│   ├── runner.py
│   ├── config.yaml
│   └── rules/
└── jvm-service/                      # Clojure web service (WORKDIR)
    ├── config.edn
    ├── resources/
    └── validation-service.jar
```

**Key Features:**
- **Multi-stage build**: Reduces final image size by ~50%
- **Single persistent pod**: Python runner created once at startup, reused for all requests
- **Relative path support**: Automatic normalization of file:// URIs for container compatibility
- **Working directory**: `/app/jvm-service` enables correct relative path resolution

**Single-instance deployment:**
```
┌────────────────────────────┐
│  Docker Container          │
│                            │
│  ┌──────────────────────┐  │
│  │ Clojure Service      │  │
│  │ (Port 8080)          │  │
│  │ - Ring + Reitit      │  │
│  │ - Swagger UI         │  │
│  └──────────────────────┘  │
│                            │
│  ┌──────────────────────┐  │
│  │ Python Runner Pod    │  │
│  │ (persistent, single) │  │
│  │ - Bencode protocol   │  │
│  │ - Rule executor      │  │
│  └──────────────────────┘  │
│                            │
│  ┌──────────────────────┐  │
│  │ Models (schemas)     │  │
│  │ - loan.schema.v1.0.0 │  │
│  └──────────────────────┘  │
└────────────────────────────┘
```

**Build and Run:**
```bash
# Build
docker build -t validation-service:latest .

# Run
docker run -d --name validation-service -p 8080:8080 validation-service:latest
```

**Deployment method:**
- Single Docker/Podman container
- Supports Docker Compose for multi-service deployments
- Health check endpoint: `/health`
- Swagger UI available at `/swagger-ui`

**Dependencies:**
- Docker or Podman runtime
- Access to coordination service (currently stubbed)
- Optional: Volume mounts for custom schemas or configuration

### Production Phase

**Packaging:**

The production service is packaged as a Docker image containing:
- Java service (Spring Boot or similar)
- Python 3.10+ runtime
- Python runner code and dependencies
- Validation rules

**Dockerfile structure:**
```dockerfile
FROM maven:3.8-openjdk-17 AS java-build
# Build Java service JAR

FROM python:3.10-slim AS python-base
# Install Python dependencies

FROM openjdk:17-slim
# Copy Java JAR
# Copy Python runtime and dependencies
# Copy validation rules
EXPOSE 8080
CMD ["java", "-jar", "validation-service.jar"]
```

**Container Orchestration:**
- Kubernetes (recommended for enterprise)
- Docker Swarm
- Cloud-native services (ECS, Cloud Run, AKS)

**Multi-instance deployment:**
```
        ┌──────────────┐
        │ Load Balancer│
        └──────┬───────┘
               │
  ┌────────────┼───────────┐
  │            │           │
┌─▼───┐     ┌──▼──┐     ┌──▼──┐
│Java │     │Java │     │Java │
│Svc  │     │Svc  │     │Svc  │
│Inst │     │Inst │     │Inst │
└─┬───┘     └──┬──┘     └──┬──┘
  │            │            │
  │ Spawn      │            │
  │ Python     │            │
  │ Runners    │            │
  │            │            │
┌─▼────────────▼────────────▼──┐
│ Centralized Logging & Metrics│
│ (ELK Stack, Prometheus, etc.)│
└──────────────────────────────┘
```

**Horizontal scaling:**
- Stateless JVM services (no shared state)
- Load balancer distributes requests
- Each container instance spawns its own Python runners
- Shared logging and metrics collection
- Auto-scaling based on CPU/memory or request metrics

**Container resource requirements:**
- CPU: 2-4 cores per container
- Memory: 2-4 GB per container (Python runners are short-lived)
- Disk: Minimal (rules in image, logs externalized)

**Deployment strategies:**
- Rolling updates: Deploy new version gradually
- Blue-green: Switch traffic between old/new versions
- Canary: Route small percentage to new version for testing

### Configuration Management

**Environment-specific configs:**
- Development: Local coordination service, verbose logging
- Staging: Staging coordination service, performance testing
- Production: Production coordination service, monitoring enabled

**Secrets management:**
- Coordination service credentials
- Logging service credentials
- Stored in environment variables or secret manager (not in config files)

## Migration Path: Clojure → Java

**See also:** [PRODUCTIONIZATION.md](./docs/PRODUCTIONIZATION.md) - Item #8 for complete production migration strategy and checklist.

### Compatibility Considerations

**Python runner:**
- Remains unchanged (same interface, same code)
- Config file format unchanged
- Rule interface unchanged

**JVM service migration:**
1. Reimplement Clojure logic in Java
2. Choose communication protocol:
   - Option A: Implement bencode in Java
   - Option B: Switch to gRPC
3. Migrate configuration format (likely no change)
4. Port monitoring and logging

**Testing strategy:**
- Run both Clojure and Java services in parallel
- Compare outputs for same inputs
- Gradual cutover with canary deployment

### Timeline

**Phase 1 - POC (Clojure):**
- Duration: 4-8 weeks
- Goal: Validate architecture, performance, rule interface
- Deliverable: Working prototype with 10-20 sample rules

**Phase 2 - Production (Java):**
- Duration: 8-12 weeks
- Goal: Enterprise-ready service with full feature set
- Deliverable: Production-deployed service with monitoring, CI/CD, documentation

## Implementation Priorities

### POC Phase (Implemented - February 2026)

**Core Infrastructure:**
✅ **Transport abstraction** - Babashka pods with pluggable ValidationRunnerClient protocol
✅ **Single persistent pod** - Created at startup, eliminates per-request spawn overhead
✅ **Entity helper abstraction** - LoanV1/V2 helpers decouple rules from data model
✅ **Rule testing framework** - 12 comprehensive tests, all passing
✅ **Rule versioning strategy** - Version numbers in filenames and config-driven selection

**API Endpoints:**
✅ **Single entity validation** - `POST /api/v1/validate`
✅ **Rule discovery** - `POST /api/v1/discover-rules`
✅ **Batch inline** - `POST /api/v1/batch` with mixed entity type support
✅ **Batch file** - `POST /api/v1/batch-file` with file://, http://, https:// URI support
✅ **Swagger UI** - Interactive API documentation at `/swagger-ui`

**Advanced Features:**
✅ **Schema-based ID mapping** - `id_fields` parameter for flexible entity correlation
✅ **Flexible output modes** - HTTP response or file output for batch operations
✅ **Relative path support** - Container-ready with automatic path normalization
✅ **Multi-stage Docker build** - Optimized image size, single persistent pod architecture

**Validation & Testing:**
✅ **Schema validation** - rule_001_v1 working with relative paths
✅ **Business rules** - rule_002_v1 and additional loan validation rules
✅ **Batch processing** - Tested with multiple entities and mixed types
✅ **Container deployment** - Docker/Podman tested and working
✅ **End-to-end tests** - Babashka test suite with 4 scenarios, all passing

### Production Roadmap

The POC validates architecture and performance. For production readiness requirements, enhancements, open questions, and implementation priorities, see:

**→ [PRODUCTIONIZATION.md](./PRODUCTIONIZATION.md)**

This document consolidates:
- Critical production requirements (authentication, monitoring, multi-version support, etc.)
- Decision framework based on POC learnings
- Open questions to resolve
- Future enhancements roadmap
- Implementation checklist

Key items deferred to production phase:
1. **Entity helper multi-version support** - See [ENTITY-HELPER-VERSIONING.md](./ENTITY-HELPER-VERSIONING.md)
2. **Field access logging** - Production-grade centralized logging (#1 in PRODUCTIONIZATION.md)
3. **Configuration management** - Dynamic reload, validation, versioning (#3)
4. **Advanced monitoring** - Distributed tracing, analytics (#6)
5. **DataProvider abstraction** - Pluggable data sources (#4)
6. **Batch optimization** - Process pooling, parallel processing (#5)

The POC phase will inform which enhancements are critical vs. optional for production.

## Appendices

### Appendix A: Bencode Format Overview

Bencode is a simple binary encoding format used by BitTorrent. It supports four data types:

- **Integers**: `i<number>e` (e.g., `i42e` = 42)
- **Strings**: `<length>:<string>` (e.g., `4:spam` = "spam")
- **Lists**: `l<items>e` (e.g., `li1ei2ee` = [1, 2])
- **Dictionaries**: `d<key><value>...e` (e.g., `d3:bar4:spam3:fooi42ee` = {"bar": "spam", "foo": 42})

Libraries available for Java and Python make encoding/decoding straightforward.

### Appendix B: Sample Rule Implementation

See section "Rule Class Interface" for complete example of `Rule001`.

### Appendix C: Glossary

- **Entity**: A data object being validated (deal, facility, loan)
- **Rule**: Executable code that checks a specific validation condition
- **Inline mode**: Real-time validation during business processes
- **Batch mode**: Scheduled validation of multiple entities
- **Pod**: Babashka pods protocol for language interoperability
- **Bencode**: Binary encoding format used by pods protocol
- **Coordination service**: External service providing additional data
- **Required data**: Additional data beyond the entity needed by a rule
- **Vocabulary term**: Standardized name for required data (e.g., "parent", "all_siblings")
- **Hierarchical rules**: Parent-child rule relationships where children only run if parent passes

### Appendix D: POC Project Structure

The following directory structure is recommended for the POC phase:

```
validation-service/
├── docs/                          # Design documentation
│   ├── DESIGN.md                  # Functional design (business-facing)
│   ├── TECHNICAL-DESIGN.md        # Technical design
│   ├── rule_field_dependencies.json  # Generated: field dependencies per rule
│   └── architecture/              # Diagrams, ADRs (Architecture Decision Records)
│
├── jvm-service/                   # Clojure orchestration service
│   ├── src/                       # Clojure source code
│   │   └── validation_service/
│   │       ├── core.clj
│   │       ├── api/               # REST API handlers and routes
│   │       ├── orchestration/     # Validation workflow logic
│   │       ├── runner/            # ValidationRunnerClient protocol and impls
│   │       └── monitoring/        # Performance tracking
│   ├── test/                      # Clojure tests
│   ├── resources/                 # Configuration files
│   │   └── config.yaml
│   ├── deps.edn                   # Dependency management
│   └── README.md                  # JVM service documentation
│
├── python-runner/                 # Python rule runner
│   ├── runner.py                  # Main entry point
│   ├── validation_engine.py       # Core validation business logic
│   ├── rule_loader.py             # Dynamic rule discovery and loading
│   ├── rule_executor.py           # Rule execution engine
│   ├── rule_test_helper.py        # Testing framework for rules
│   ├── cache.py                   # Simple caching for entity/required data
│   ├── entity_helpers/            # Entity helper classes (wrappers for data model access)
│   │   ├── __init__.py            # Exports Loan, Facility, Deal, create_entity_helper
│   │   ├── base.py                # Shared base class and utilities (optional)
│   │   ├── loan_v1.py                # Loan helper class
│   │   ├── facility.py            # Facility helper class
│   │   └── deal.py                # Deal helper class
│   ├── transport/                 # Transport abstraction layer
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract TransportHandler interface
│   │   ├── pods_transport.py      # Babashka pods implementation
│   │   └── grpc_transport.py      # gRPC implementation (future)
│   ├── rules/                     # Validation rules
│   │   ├── loan/
│   │   │   ├── rule_001_v1.py
│   │   │   ├── rule_001_v1_test.py
│   │   │   ├── rule_042_v1.py
│   │   │   └── rule_055_v1.py
│   │   ├── facility/
│   │   │   ├── rule_003_v1.py
│   │   │   └── rule_017_v1.py
│   │   └── deal/
│   │       └── rule_010_v1.py
│   ├── config.yaml                # Rule configuration
│   ├── requirements.txt           # Python dependencies
│   └── README.md                  # Python runner documentation
│
├── models/                        # JSON Schema definitions
│   ├── loan.schema.v1.0.0.json    # Loan entity schema v1
│   ├── loan.schema.v2.0.0.json    # Loan entity schema v2
│   ├── facility.schema.json       # Facility entity schema
│   └── deal.schema.json           # Deal entity schema
│   # NOTE: Schemas are versioned and stored alongside code.
│   # Entity data contains a $schema field that determines which version applies.
│
├── config/                        # Environment-specific configurations
│   ├── dev.yaml                   # Development environment
│   ├── staging.yaml               # Staging environment
│   └── poc.yaml                   # POC demo environment
│
├── scripts/                       # Development and deployment utilities
│   ├── start-services.sh          # Start both JVM and Python services
│   ├── run-tests.sh               # Run all tests (JVM + Python)
│   ├── load-sample-data.sh        # Load demo data for testing
│   ├── validate-config.sh         # Validate configuration files
│   └── catalog_rule_dependencies.sh  # Analyze which fields each rule accesses
│
├── sample-data/                   # Test and demo data
│   ├── deals.json                 # Sample deals for testing
│   ├── facilities.json            # Sample facilities
│   ├── loans.json                 # Sample loans
│   ├── single-examples/           # Individual entity examples
│   │   └── loan1.json
│   └── batch_examples/            # Batch file examples
│       ├── batch_100_loans.json
│       └── batch_1000_loans.json
│
├── logs/                          # Runtime logs
│   # Field access tracking logs from entity helpers
│   # Service logs during development/testing
│   # NOTE: .gitignore should exclude log files
│
├── docker/                        # Container definitions (optional)
│   ├── Dockerfile.jvm             # JVM service container
│   ├── Dockerfile.python          # Python runner container
│   └── docker-compose.yml         # Multi-container orchestration
│
└── README.md                      # Project overview and getting started guide
```

**Structure Rationale:**

**Separation of Concerns:**
- `jvm-service/` and `python-runner/` are independent, self-contained projects
- Each can be built, tested, and run independently
- Clear ownership boundaries between orchestration and rule execution

**Configuration Management:**
- `config/` directory separate from code enables environment-specific settings
- Python runner's `config.yaml` defines rule sets (inline vs batch)
- JVM service configuration in `resources/config.yaml` or `config/` directory

**Developer Productivity:**
- `scripts/` provides common tasks (start services, run tests)
- `sample-data/` enables quick testing and demos
- `docker/` (optional) ensures consistent environments

**Documentation:**
- `docs/` keeps design documents organized
- Each service has its own README for specific setup/usage
- Root README provides overall project context

**Testing:**
- Tests colocated with code (`jvm-service/test/`, rule test files)
- Sample data available for integration testing
- Test helper framework in `python-runner/rule_test_helper.py`

**Migration Path:**
- Structure supports easy swap of `jvm-service/` for Java implementation
- Python runner remains unchanged during JVM migration
- Clear boundaries enable parallel development

**POC Focus:**
- Simple, flat structure suitable for small team
- Easy to navigate and understand
- No over-engineering (can refactor for production if needed)

**Getting Started Flow:**

For a new developer joining the POC:
1. Read `README.md` (project overview)
2. Review `docs/DESIGN.md` and `docs/TECHNICAL-DESIGN.md`
3. Run `scripts/start-services.sh`
4. Test with `sample-data/loans.json`
5. Write a new rule in `python-runner/rules/loan/`
6. Test with `python-runner/rule_test_helper.py`

This structure balances simplicity for POC with enough organization to support growth into production.

---

**Document Version:** 2.0
**Last Updated:** 2026-02-12
**Authors:** Technical Architecture Team
**Status:** ✅ Phase 1 POC Implementation Complete

**Implementation Summary:**
- All core endpoints implemented and tested
- Batch validation with mixed types and flexible output
- Container-ready with multi-stage Docker build
- Single persistent pod architecture for optimal performance
- Comprehensive test coverage (Python + integration tests)
- Production-ready for small-to-medium scale deployments
