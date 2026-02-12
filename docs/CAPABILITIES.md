# Validation Service - Component Capabilities

## Document Purpose

This document provides a clear separation of responsibilities between the Python and JVM components of the validation service. Understanding this division is essential for:
- Architecture comprehension
- Development work allocation
- Migration planning (Clojure → Java)
- Troubleshooting and debugging

---

## Python Runner (python-runner/)

**Core Function:** Rule execution and validation logic

### Capabilities

- ✅ **Rule execution** - Runs validation rules against entities
- ✅ **Rule loading** - Dynamic discovery and loading of rule classes from filesystem
- ✅ **Entity helpers** - Data model abstraction layer (Loan, Facility, Deal classes)
- ✅ **Required data introspection** - Determines what additional data rules need
- ✅ **Field dependency introspection** - Returns structured `(logical_name, physical_path)` pairs per rule via `get-field-dependencies` pod function
- ✅ **Field access tracking** - Tracks which entity helper properties each rule touches during execution
- ✅ **Transport layer** - Pods/gRPC communication interface (abstracted)
- ✅ **Hierarchical execution** - Manages parent-child rule dependencies
- ✅ **Caching** - In-memory caching of entity and required data during validation

### Key Characteristics

- **Language:** Python 3.10+
- **Entry Point:** `runner.py`
- **Configuration:** `config.yaml` (defines rule sets for inline/batch modes)
- **Stateless:** Each spawned process handles one validation job
- **Transport Agnostic:** Business logic independent of communication protocol
- **Migration Stable:** Remains unchanged during JVM migration (Clojure → Java)

### What Python Does NOT Do

- ❌ Expose REST APIs
- ❌ Manage processes
- ❌ Fetch data from coordination service
- ❌ Handle HTTP requests
- ❌ Aggregate results across entities
- ❌ Centralized logging (only local field access logging)

**Key Point:** Contains ALL validation business logic. The Python runner is the "brain" that knows how to validate.

---

## Clojure/JVM Service (jvm-service/)

**Core Function:** Orchestration and API gateway

### Capabilities

- ✅ **REST API** - Expose validation endpoints (POST /api/v1/validate, /api/v1/validate/batch)
- ✅ **Workflow orchestration** - Coordinate two-phase validation flow:
  1. Get required data from Python
  2. Fetch required data from coordination service
  3. Execute validation with Python
- ✅ **Process management** - Spawn and manage Python runner processes per validation job
- ✅ **Data fetching** - Call external coordination service to fetch required data
- ✅ **Result aggregation** - Collect and format validation results from Python
- ✅ **Monitoring** - Track performance metrics and rule execution times
- ✅ **Alerting** - Trigger alerts on performance threshold violations
- ✅ **Logging** - Centralized validation result logging to enterprise systems
- ✅ **Transport client** - Communicate with Python via pods/gRPC (abstracted)

### Key Characteristics

- **Language (POC):** Clojure 1.11+
- **Language (Production):** Java 17+ (Spring Boot)
- **Entry Point:** `core.clj` (POC) / `Application.java` (Production)
- **Configuration:** `config.yaml` (service settings, coordination service URL, etc.)
- **Stateless:** No shared state between requests
- **Horizontally Scalable:** Multiple instances can run behind load balancer
- **Migration Target:** Will be rewritten from Clojure to Java for production

### What JVM Does NOT Do

- ❌ Execute validation rules
- ❌ Load or understand rule logic
- ❌ Access entity data directly (only passes through)
- ❌ Know about data model structure (relies on Python helpers)
- ❌ Field-level validation logic

**Key Point:** Contains NO validation logic. Pure orchestration. The JVM service is the "coordinator" that manages workflow.

---

## Communication Between Components

### Transport Abstraction

Both sides abstract the communication protocol:

**JVM Side:**
- Interface: `ValidationRunnerClient` (protocol in Clojure, interface in Java)
- Implementations: `PodsRunnerClient`, `GrpcRunnerClient` (future)

**Python Side:**
- Interface: `TransportHandler` (abstract base class)
- Implementations: `PodsTransportHandler`, `GrpcTransportHandler` (future)

### Protocol Functions

**Phase 1: Get Required Data**
```
JVM → Python: get_required_data(entity_type, schema_url, mode)
Python → JVM: ["parent", "all_siblings", "client_reference_data"]

Note: schema_url determines which version-specific rules to load.
      "schema" is NOT a valid vocabulary term.
```

**Phase 2: Execute Validation**
```
JVM → Python: validate(entity_type, entity_data, mode, required_data)
Python → JVM: {hierarchical validation results}
```

**Introspection: Field Dependencies**
```
JVM → Python: get_field_dependencies(entity_type, entity_data, mode)
Python → JVM: {"rule_002_v1": [["principal", "financial.principal_amount"], ...]}
```

---

## Clean Separation of Concerns

| Concern | Python Runner | JVM Service |
|---------|--------------|-------------|
| **Validation Logic** | ✅ Owns | ❌ None |
| **Rule Management** | ✅ Loads/executes | ❌ None |
| **Data Model Knowledge** | ✅ Entity helpers | ❌ Opaque passthrough |
| **API Layer** | ❌ None | ✅ REST endpoints |
| **Process Management** | ❌ None | ✅ Spawn/manage Python |
| **External Data Fetch** | ❌ None | ✅ Coordination service |
| **Monitoring/Metrics** | ❌ None | ✅ Performance tracking |
| **Centralized Logging** | ❌ None | ✅ Result logging |
| **Transport Protocol** | ✅ Abstracted | ✅ Abstracted |

---

## Mental Model

### Python Runner (Validation Engine)
**"How to validate"**
- Knows rules
- Knows data structure
- Knows business logic
- Answers: "Is this loan valid?"

### JVM Service (Orchestrator)
**"How to coordinate"**
- Knows workflow
- Knows external systems
- Knows performance requirements
- Answers: "Get me a validation result for this loan"

### Analogy
- **Python** = Expert consultant who performs the analysis
- **JVM** = Project manager who coordinates the consultant and delivers results to clients

---

## Migration Implications

### Clojure → Java Migration (JVM Service Only)

**What Changes:**
- JVM service rewritten in Java (Clojure → Spring Boot)
- Transport client reimplemented in Java
- Orchestration logic ported to Java

**What Stays the Same:**
- ✅ Python runner (100% unchanged)
- ✅ Rule interface
- ✅ Validation logic
- ✅ Entity helpers
- ✅ Protocol (get_required_data, validate)
- ✅ Configuration format

**Why This Works:**
- Clean abstraction boundaries
- Transport layer abstracted on both sides
- No shared code between JVM and Python
- Protocol is language-agnostic

**Testing Strategy:**
- Run Clojure and Java services in parallel
- Compare outputs for same inputs
- Validate identical behavior before cutover

---

## Development Guidelines

### Working on Validation Logic?
→ **Edit Python code** in `python-runner/`
- Add new rules in `rules/{entity_type}/`
- Modify entity helpers in `entity_helpers/`
- Update rule configuration in `config.yaml`

### Working on API or Orchestration?
→ **Edit JVM code** in `jvm-service/`
- Modify REST endpoints
- Change workflow logic
- Update coordination service integration
- Adjust monitoring/logging

### Working on Communication Protocol?
→ **Edit both sides** (maintain interface compatibility)
- Update `ValidationRunnerClient` protocol/interface (JVM)
- Update `TransportHandler` abstract class (Python)
- Ensure both implementations stay in sync

---

**Document Version:** 1.1
**Last Updated:** 2026-02-08
**Status:** Reference Documentation
