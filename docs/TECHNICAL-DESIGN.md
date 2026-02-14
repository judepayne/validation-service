# Validation Service - Technical Design

## Document Purpose

This document describes the technical architecture and implementation of the validation service POC. It is intended for software engineers, architects, and technical stakeholders who need to understand, maintain, or productionize the system.

For functional requirements and business context, see [DESIGN-OVERVIEW.md](../DESIGN-OVERVIEW.md).
For production migration planning, see [PRODUCTIONIZATION.md](PRODUCTIONIZATION.md).

---

## 1. System Overview

The validation service validates business data (deals, facilities, loans) against configurable rule sets. It uses a two-component architecture: a **JVM orchestration service** (Clojure) coordinating a **Python validation engine** via the babashka pods protocol.

### Implementation Phases

**Phase 1 - POC (Current, Complete):**
- JVM Service: Clojure with Ring/Reitit
- Rule Engine: Python 3.10+
- Communication: Babashka pods (bencode over stdin/stdout)
- Data Model: JSON Schema
- Packaging: Docker container

**Phase 2 - Production:**
- JVM Service: Java (Spring Boot)
- Rule Engine: Python (unchanged)
- Communication: gRPC (or retained bencode, based on performance needs)
- See [PRODUCTIONIZATION.md](PRODUCTIONIZATION.md) for the migration roadmap

---

## 2. Architecture

### High-Level Components

```
           ┌─────────────┐
           │   Client    │
           │   Systems   │
           └──────┬──────┘
                  │ HTTP/REST
                  │
┌─────────────────▼──────────────────────────────┐
│                                                │
│       JVM Orchestration Service                │
│           (Clojure POC → Java)                 │
│                                                │
│  ┌────────────────┐   ┌─────────────────────┐  │
│  │  Web Layer     │   │   Library Layer     │  │
│  │  (Ring/Reitit) │──▶│   (Core Logic)      │  │
│  └────────────────┘   └──────────┬──────────┘  │
│                                  │             │
└──────────────────────────────────┼─────────────┘
              │                    │
              │ HTTP/REST          │ Bencode/Pods
              │                    │
   ┌──────────▼──────────┐   ┌────▼────────────┐
   │  Coordination       │   │  Python Rule     │
   │  Service            │   │  Runner          │
   │  (External, stub)   │   │                  │
   │                     │   │  ┌────────────┐  │
   │  Provides related   │   │  │ Rules      │  │
   │  data for rules     │   │  │ • loan/    │  │
   └─────────────────────┘   │  │ • fac.../  │  │
                             │  │ • deal/    │  │
                             │  └────────────┘  │
                             └──────────────────┘
```

### Separation of Concerns

| Concern | JVM Service | Python Runner |
|---------|-------------|---------------|
| REST API | Owns | None |
| Workflow orchestration | Owns | None |
| Process management | Owns | None |
| External data fetching | Owns | None |
| Validation logic | None | Owns |
| Rule loading & execution | None | Owns |
| Data model knowledge | Opaque passthrough | Entity helpers |
| Transport protocol | Abstracted | Abstracted |

The JVM service is the **coordinator** ("get me a validation result"). The Python runner is the **engine** ("here is how to validate"). Neither knows the other's internals; they communicate through a well-defined protocol.

---

## 3. Project Structure

Understanding the directory layout is essential context for the sections that follow.

```
validation-service/
├── README.md
├── DESIGN-OVERVIEW.md
├── Dockerfile
│
├── logic/                                 # Business-owned assets (rules team)
│   ├── business-config.yaml               #   Tier 2: Business configuration
│   ├── models/                            #   JSON Schemas
│   │   ├── loan.schema.v1.0.0.json
│   │   └── loan.schema.v2.0.0.json
│   ├── rules/                             #   Rule implementations
│   │   ├── base.py                        #     ValidationRule ABC
│   │   └── loan/
│   │       ├── rule_001_v1.py             #     JSON Schema validation
│   │       ├── rule_002_v1.py             #     Financial soundness
│   │       ├── rule_003_v1.py             #     Status validation
│   │       └── rule_004_v1.py             #     Balance constraints
│   └── entity_helpers/                    #   Data model abstraction
│       ├── __init__.py                    #     create_entity_helper factory
│       ├── version_registry.py            #     Schema URL → helper routing
│       ├── loan_v1.py                     #     LoanV1 for schema v1.0.0
│       └── loan_v2.py                     #     LoanV2 for schema v2.0.0
│
├── docs/
│   ├── TECHNICAL-DESIGN.md
│   ├── TECHNICAL-DESIGN.md                # This document
│   ├── CAPABILITIES.md
│   ├── HOW-VERSIONING-WORKS.md
│   ├── POD-VS-GRPC.md
│   ├── LIBRARY-USAGE.md
│   └── PRODUCTIONIZATION.md
│
├── python-runner/
│   ├── runner.py                          # Entry point (pod protocol loop)
│   ├── local-config.yaml                  # Tier 1: Infrastructure config
│   ├── requirements.txt
│   ├── core/
│   │   ├── validation_engine.py
│   │   ├── rule_executor.py
│   │   ├── rule_loader.py
│   │   ├── config_loader.py
│   │   ├── rule_fetcher.py
│   │   └── logic_fetcher.py          # Remote logic package fetching
│   ├── transport/
│   │   ├── base.py
│   │   ├── pods_transport.py
│   │   ├── bencode_reader.py
│   │   └── case_conversion.py
│   └── tests/
│       └── ...
│
├── jvm-service/
│   ├── deps.edn
│   ├── build.clj
│   ├── resources/
│   │   ├── library-config.edn
│   │   ├── web-config.edn
│   │   └── logback.xml
│   ├── src/validation_service/
│   │   ├── core.clj
│   │   ├── config.clj
│   │   ├── library/api.clj
│   │   ├── api/{routes,handlers,schemas}.clj
│   │   ├── orchestration/{workflow,coordination}.clj
│   │   ├── runner/{protocol,pods_client}.clj
│   │   └── utils/file_io.clj
│   └── test/
│       └── ...
│
└── sample-data/
    └── single-examples/loan1.json
```

### The `logic/` Folder

The `logic/` directory consolidates all business-owned assets: the business configuration, rule implementations, entity helpers, and data model schemas. This is a deliberate **layer of indirection** — the Python runner's `local-config.yaml` (Tier 1) points to `logic/business-config.yaml` (Tier 2) via `business_config_uri`, which in turn references rules and schemas within `logic/`.

This indirection means the entire `logic/` folder could live in a separate repository, be mounted from a different location, or be fetched from a remote CDN. The service code has no hardcoded knowledge of what's inside `logic/`; it discovers everything through the configuration chain. In production, the rules team owns `logic/` and the service team owns everything else — the two can be versioned and deployed independently.

#### Immutability Model

The architecture relies on a strict immutability contract for the files inside `logic/`:

**Immutable (never edited in place):**
- **Rules** (`rules/loan/rule_001_v1.py`) — a rule file, once published, is frozen. Changes are published as new versions (`rule_001_v2.py`) with corresponding updates to business-config.yaml.
- **Entity helpers** (`entity_helpers/loan_v1.py`) — a helper maps logical properties to a specific schema version's physical fields. When the schema evolves, a new helper is created (`loan_v2.py`), never a modified `loan_v1.py`.
- **Model schemas** (`models/loan.schema.v1.0.0.json`) — schemas are versioned artifacts. A published schema is immutable; breaking changes produce a new major version.

**Mutable (the routing layer):**
- **Business config** (`business-config.yaml`) — this is the single file that *is* allowed to change in place. It controls which rules are active, which schema versions map to which helpers, and how rulesets are composed. Editing it is how the rules team "deploys": add a new rule version to a ruleset, point a schema to a new helper, or reorganize rule hierarchies.

This division makes the system safe for remote serving and caching. Immutable files can be cached aggressively (or indefinitely) — their content never changes for a given filename. The business config is the only file that needs freshness checks, and it's small (a few KB of YAML). Since the entire `logic/` folder is typically in a git repository, changes to business-config.yaml are tracked, reviewed, and auditable just like code changes.

#### Local vs Remote Serving

The `LogicPackageFetcher` (in `python-runner/core/logic_fetcher.py`) determines how to serve `logic/` at startup based on the `business_config_uri` in local-config.yaml:

| `business_config_uri` | Mode | Behavior |
|------------------------|------|----------|
| `../logic/business-config.yaml` | Local | Resolve to absolute directory, use directly. No fetching, no caching. This is the development workflow. |
| `https://cdn.example.com/logic/business-config.yaml` | Remote | Parse the config, derive all required file paths, fetch each into a local cache mirroring `logic/`, use cache as `logic_dir`. |

**No manifest file is needed.** The business config already enumerates everything: rule IDs in `*_rules` sections map to rule files, helper class references in `schema_to_helper_mapping` map to helper files, and a small set of structural files (`rules/base.py`, `entity_helpers/__init__.py`, `entity_helpers/version_registry.py`) are always included. The `LogicPackageFetcher.derive_required_files()` method parses the config and produces the complete file list.

The base URI is computed by stripping the filename from `business_config_uri` — if the config is at `https://cdn.example.com/logic/business-config.yaml`, then rules are at `https://cdn.example.com/logic/rules/loan/rule_001_v1.py`. No additional configuration key is required.

In the cached directory, the structure mirrors `logic/` exactly, so `sys.path` points at the cache root and all imports (`from rules.base import ValidationRule`, `from entity_helpers import create_entity_helper`) work unchanged.

---

## 4. JVM Service Architecture

### Library + Web Split

The JVM service is structured as two layers, separating reusable logic from HTTP transport (see [LIBRARY-USAGE.md](LIBRARY-USAGE.md) for embedded usage).

```
┌────────────────────────────────────────────────────────┐
│  Web Layer (validation-service.api.*)                  │
│  Routes, handlers, Swagger UI, middleware, Jetty       │
│  Config: web-config.edn                                │
│                                                        │
│  Calls ▼ ValidationService protocol methods            │
├────────────────────────────────────────────────────────┤
│  Library Layer (validation-service.library.*)          │
│  ValidationService protocol, workflow orchestration,   │
│  runner client, coordination client                    │
│  Config: library-config.edn                            │
│  Returns: raw data structures (maps/vectors)           │
└────────────────────────────────────────────────────────┘
```

**Library Layer** — zero HTTP dependencies. Can be embedded in batch jobs, streaming pipelines, or other JVM applications.

**Web Layer** — wraps library methods in Ring responses, adds Swagger docs, CORS, and request logging.

### Source Layout

```
jvm-service/src/validation_service/
├── core.clj                    # Application entry point
├── config.clj                  # Configuration loading (aero)
├── library/
│   └── api.clj                 # ValidationService protocol + impl
├── api/
│   ├── routes.clj              # Reitit route definitions + Swagger
│   ├── handlers.clj            # HTTP request handlers
│   └── schemas.clj             # OpenAPI request/response examples
├── orchestration/
│   ├── workflow.clj            # Validation workflow logic
│   └── coordination.clj        # Coordination service client (stub)
├── runner/
│   ├── protocol.clj            # ValidationRunnerClient protocol
│   └── pods_client.clj         # Babashka pods implementation
└── utils/
    └── file_io.clj             # URI normalization, file fetching
```

### ValidationService Protocol

The core public API, defined in `library/api.clj`:

```clojure
(defprotocol ValidationService
  (validate [this entity-type entity-data ruleset-name])
  (discover-rules [this entity-type schema-url ruleset-name])
  (batch-validate [this entities id-fields ruleset-name])
  (batch-file-validate [this file-uri entity-types id-fields ruleset-name]))
```

`ValidationServiceImpl` holds a `runner-client` and `config`, delegating each method to workflow functions in `orchestration/workflow.clj`.

### ValidationRunnerClient Protocol

Abstracts JVM-to-Python communication (`runner/protocol.clj`):

```clojure
(defprotocol ValidationRunnerClient
  (get-required-data [this entity-type schema-url ruleset-name])
  (validate [this entity-type entity-data ruleset-name required-data])
  (discover-rules [this entity-type entity-data ruleset-name]))
```

`PodsRunnerClient` implements this via `babashka.pods/invoke`. A future `GrpcRunnerClient` would implement the same protocol — no workflow changes needed.

### Configuration

**Library config** (`jvm-service/resources/library-config.edn`):

```clojure
{:python_runner
 {:executable "python3"
  :script_path "../python-runner/runner.py"
  :config_path "../python-runner/local-config.yaml"
  :spawn_timeout_ms 5000
  :validation_timeout_ms 30000
  :pool_size 5}

 :coordination_service
 {:base_url "http://localhost:8081"
  :timeout_ms 5000
  :retry_attempts 3
  :circuit_breaker_enabled true}}
```

**Web config** (`jvm-service/resources/web-config.edn`):

```clojure
{:service {:port 8080 :host "0.0.0.0"}
 :cors {:enabled true :allowed_origins ["http://localhost:3000"]}
 :logging {:level :info}
 :monitoring {:metrics_enabled true :health_check_enabled true}}
```

### Technology Stack

| Component | Library |
|-----------|---------|
| HTTP server | Ring + Jetty |
| Routing | Reitit (data-driven) |
| API docs | Reitit Swagger + Swagger UI |
| JSON | Cheshire |
| Pod communication | babashka/pods |
| HTTP client | clj-http |
| Configuration | Aero |
| Logging | tools.logging + Logback |

---

## 5. Python Runner Architecture

### Source Layout

```
python-runner/
├── runner.py                    # Entry point (pod protocol loop)
├── local-config.yaml            # Tier 1: Infrastructure config
├── requirements.txt             # Dependencies
├── core/
│   ├── validation_engine.py     # Main orchestration
│   ├── rule_executor.py         # Hierarchical rule execution
│   ├── rule_loader.py           # Dynamic rule discovery
│   ├── config_loader.py         # Two-tier config loading
│   ├── rule_fetcher.py          # Remote rule fetching + caching
│   └── logic_fetcher.py         # Remote logic package fetching
├── transport/
│   ├── base.py                  # Abstract TransportHandler
│   ├── pods_transport.py        # Babashka pods implementation
│   ├── bencode_reader.py        # Stream-aware bencode parser
│   └── case_conversion.py       # kebab-case ↔ snake_case
└── tests/
    ├── test_rule_executor.py
    ├── test_entity_helper_integration.py
    ├── test_rule_discovery.py
    └── ...
```

### Entry Point (`runner.py`)

The runner bootstraps the logic directory, initializes a `ValidationEngine` and a `PodsTransportHandler`, then enters a request loop:

```python
# Bootstrap: resolve logic directory (local or remote)
fetcher = LogicPackageFetcher()
logic_dir = fetcher.resolve_logic_dir(config_path)
sys.path.insert(0, logic_dir)

# Initialize and run
engine = ValidationEngine(config_path)
transport = PodsTransportHandler()  # Pluggable: could be GrpcTransportHandler
transport.start()

while True:
    request_id, function_name, args = transport.receive_request()
    # Dispatch to engine method based on function_name
    # Send response or error via transport
```

The bootstrap step resolves `logic/` to either a local directory (development) or a cached copy of a remote package (production). The transport is injected — switching to gRPC means replacing one line, with zero changes to validation logic.

### ValidationEngine

Central orchestration class (`core/validation_engine.py`). Manages config loading, rule loading, and dispatches to the rule executor.

**Pod-exposed functions:**

| Function | Purpose | Input | Output |
|----------|---------|-------|--------|
| `get-required-data` | Introspect rules for external data needs | entity_type, schema_url, ruleset_name | `["parent", "all_siblings", ...]` |
| `validate` | Execute rules against entity | entity_type, entity_data, ruleset_name, required_data | Hierarchical result list |
| `discover-rules` | Return rule metadata with field dependencies | entity_type, entity_data, ruleset_name | Map of rule_id → metadata |

**Rule routing logic** (`_get_rules_for_ruleset`):
1. Look up `{ruleset_name}_rules` in business config
2. Try schema URL key first (version-specific rules)
3. Fall back to entity type key (backward compatibility)

### RuleExecutor

Executes rules hierarchically with timing (`core/rule_executor.py`):

1. For each rule in the config list, inject the entity helper and required data
2. Call `rule.run()` with timing
3. If PASS and rule has children → execute children recursively
4. If FAIL/NORUN → mark all children as NORUN ("Parent rule did not pass")
5. If exception → status = ERROR with traceback message

Result structure:

```json
{
  "rule_id": "rule_001_v1",
  "description": "JSON Schema validation",
  "status": "PASS",
  "message": "",
  "execution_time_ms": 12.5,
  "children": [
    {
      "rule_id": "rule_004_v1",
      "status": "NORUN",
      "message": "Parent rule did not pass, rule skipped",
      "children": []
    }
  ]
}
```

### RuleLoader

Dynamic rule discovery (`core/rule_loader.py`). Uses filename as the single source of truth for rule identity:

- Config specifies `rule_id: rule_001_v1`
- Loader searches `logic/rules/{entity_type}/rule_001_v1.py`
- Imports the module, finds class `Rule` (standard name for all rules)
- Instantiates with injected ID: `Rule("rule_001_v1")`
- Caches the class for subsequent loads

Supports two modes:
- **Path mode** (development): searches local `logic/rules/` directory
- **URI mode** (production): uses `ConfigLoader.resolve_rule_uri()` + `RuleFetcher` for remote rules

### Dependencies

```
bencodepy>=0.9.5      # Babashka pods bencode protocol
PyYAML>=6.0           # Configuration parsing
jsonschema>=4.17.0    # JSON Schema validation (used by rule_001_v1)
```

---

## 6. Communication Protocol

### Babashka Pods (POC)

The JVM spawns the Python runner as a child process. They communicate via bencode-encoded messages over stdin/stdout.

```
┌───────────┐    bencode/stdin/stdout    ┌──────────────┐
│  Clojure  │◄──────────────────────────►│   Python     │
│  JVM      │     (process spawn)        │   Runner     │
└───────────┘                            └──────────────┘
```

**Message flow:**

1. JVM calls `pods/load-pod ["python3" "runner.py" "local-config.yaml"]`
2. Python sends `describe` response (namespace, available functions)
3. JVM sends `invoke` messages; Python responds with `value` or `error`
4. Pod stays alive across multiple requests (single persistent process)

**Invoke message format:**
```
{op: "invoke", id: "req-1", var: "validate", args: {...}}
→ {id: "req-1", value: "[{...json results...}]", status: ["done"]}
```

The `format: "json"` declaration in `describe` means values are JSON-encoded strings within bencode, automatically parsed by the pods library.

### Case Conversion

Clojure uses kebab-case (`get-required-data`), Python uses snake_case (`get_required_data`). The transport layer handles conversion in both directions via `case_conversion.py`.

### Transport Abstraction

Both sides abstract the protocol behind interfaces:

**JVM:** `ValidationRunnerClient` protocol → `PodsRunnerClient` (or future `GrpcRunnerClient`)

**Python:** `TransportHandler` ABC → `PodsTransportHandler` (or future `GrpcTransportHandler`)

```python
class TransportHandler(ABC):
    @abstractmethod
    def start(self): ...
    @abstractmethod
    def send_response(self, request_id: str, result: Any): ...
    @abstractmethod
    def send_error(self, request_id: str, error: str): ...
    @abstractmethod
    def receive_request(self) -> tuple[str, str, Dict[str, Any]]: ...
```

The `ValidationEngine` receives the same dict structures regardless of transport. See [POD-VS-GRPC.md](POD-VS-GRPC.md) for a detailed protocol comparison and migration plan.

---

## 7. Two-Tier Configuration

### Motivation

Production deployments need separation of concerns: the **service team** owns infrastructure settings, the **rules team** owns business logic. These should be independently versioned and deployed.

### Architecture

```
Tier 1: Infrastructure                  Tier 2: Business Logic
(service team)                           (rules team, inside logic/)

┌─────────────────────────┐             ┌─────────────────────────┐
│ python-runner/          │             │ logic/                  │
│   local-config.yaml     │────────────▶│   business-config.yaml  │
│                         │  references │                         │
│ • business_config_uri   │             │ • Rule set definitions  │
│ • logic_cache_dir       │             │ • Schema→helper mapping │
│                         │             │ • Version compatibility │
└─────────────────────────┘             │ • rules_base_uri (opt)  │
                                        │                         │
                                        │   rules/                │
                                        │   models/               │
                                        └─────────────────────────┘
```

### Tier 1: Local Config (`python-runner/local-config.yaml`)

```yaml
business_config_uri: "../logic/business-config.yaml"   # or https://...
logic_cache_dir: "/tmp/validation-cache"              # only used for remote URIs
```

The `business_config_uri` is a **layer of indirection**: it points from the service's infrastructure config into the `logic/` directory where all business-owned assets reside. This URI supports relative paths, `file://`, `http://`, and `https://` — meaning `logic/` could be a local directory, a mounted volume, or a remote CDN. Remote configs are fetched and cached by `ConfigLoader` using SHA256-keyed files.

### Tier 2: Business Config (`logic/business-config.yaml`)

```yaml
# Rule set definitions (schema-version-specific)
quick_rules:
  "https://bank.example.com/schemas/loan/v1.0.0":
    - rule_id: rule_001_v1
    - rule_id: rule_002_v1
  loan:   # Fallback for entities without $schema
    - rule_id: rule_001_v1

thorough_rules:
  "https://bank.example.com/schemas/loan/v1.0.0":
    - rule_id: rule_001_v1
    - rule_id: rule_002_v1
    - rule_id: rule_003_v1
      children:
        - rule_id: rule_004_v1    # Only runs if rule_003 passes

# Schema URL → entity helper class mapping
schema_to_helper_mapping:
  "https://bank.example.com/schemas/loan/v1.0.0": "loan_v1.LoanV1"
  "https://bank.example.com/schemas/loan/v2.0.0": "loan_v2.LoanV2"

# Fallback when $schema is absent
default_helpers:
  loan: "loan_v1.LoanV1"

# Version compatibility
version_compatibility:
  allow_minor_version_fallback: true   # v1.1.0 → v1.0.0 helper
  strict_major_version: true           # Unknown major → error
```

### Production Deployment

```yaml
# local-config.yaml (production)
business_config_uri: "https://rules-cdn.example.com/prod/business-config.yaml"

# business-config.yaml (hosted remotely)
rules_base_uri: "https://rules-cdn.example.com/prod/rules"
```

Rules are fetched via `RuleFetcher` with SHA256-based caching in `logic_cache_dir`. The rules team can deploy new rules independently of the service.

### Remote Logic Package Fetching

When `business_config_uri` points to a remote URL, the `LogicPackageFetcher` fetches the entire `logic/` package into a local cache at startup. The file list is derived from `business-config.yaml` itself — no manifest needed. See [The `logic/` Folder](#the-logic-folder) in Section 3 for the full design, including the immutability model that makes this safe.

**Production configuration:**
```yaml
# local-config.yaml — the only change needed
business_config_uri: "https://rules-cdn.example.com/prod/logic/business-config.yaml"
```

This single URI change makes the service fetch the entire logic package from the CDN. The rules team publishes to the CDN; the service team deploys nothing.

---

## 8. Validation Rules

### Rule Base Class

All rules inherit from `ValidationRule` (`logic/rules/base.py`):

```python
class ValidationRule(ABC):
    def __init__(self, rule_id: str): ...
    def get_id(self) -> str: ...

    @abstractmethod
    def validates(self) -> str: ...           # Entity type ("loan")
    @abstractmethod
    def required_data(self) -> list[str]: ... # ["parent", "all_siblings"]
    @abstractmethod
    def description(self) -> str: ...         # Plain English
    @abstractmethod
    def set_required_data(self, data: dict) -> None: ...
    @abstractmethod
    def run(self) -> tuple[str, str]: ...     # (status, message)
```

**Status values:** PASS, FAIL, NORUN, ERROR

The rule executor injects `self.entity` (an entity helper instance) before calling `run()`. Rules access data through the helper's logical properties, never via raw dict access.

### Rule File Conventions

- **Location:** `logic/rules/{entity_type}/rule_{id}_v{version}.py`
- **Class name:** Always `Rule` (standard across all rules)
- **Rule ID:** Derived from filename by the loader (`rule_001_v1.py` → `rule_001_v1`)
- **Versioning:** New version = new file (`rule_001_v2.py`), config selects which to use

### Implemented Rules (Loans)

| Rule | Description | Required Data |
|------|-------------|---------------|
| `rule_001_v1` | JSON Schema validation against `$schema` | None |
| `rule_002_v1` | Financial soundness (principal > 0, maturity > inception, balance ≤ principal, rate ≥ 0) | None |
| `rule_003_v1` | Status must be valid (active, paid_off, defaulted, written_off) | None |
| `rule_004_v1` | Balance constraints (paid_off → zero balance, active → non-zero) | None |

### Hierarchical Execution

Rules can be organized as parent-child in configuration:

```yaml
thorough_rules:
  "https://bank.example.com/schemas/loan/v1.0.0":
    - rule_id: rule_003_v1        # Parent: status validation
      children:
        - rule_id: rule_004_v1    # Child: balance constraints
```

If the parent fails, all children are marked NORUN. This models prerequisites: "don't check balance constraints if the status itself is invalid."

### Required Data Vocabulary

Rules declare external data needs using vocabulary terms:

- **Hierarchical:** `parent`, `all_children`, `all_siblings`
- **Related:** `client_reference_data`, `related_parties`

The JVM service fetches this data from the coordination service (currently stubbed) and passes it to the Python runner for injection into rules via `set_required_data()`.

### Writing a New Rule

1. Create `logic/rules/loan/rule_005_v1.py`:
   ```python
   from rules.base import ValidationRule

   class Rule(ValidationRule):
       def validates(self) -> str:
           return "loan"

       def required_data(self) -> list[str]:
           return []

       def description(self) -> str:
           return "Loan currency must be a supported currency"

       def set_required_data(self, data: dict) -> None:
           pass

       def run(self) -> tuple[str, str]:
           supported = {"USD", "EUR", "GBP", "JPY"}
           if self.entity.currency not in supported:
               return ("FAIL", f"Unsupported currency: {self.entity.currency}")
           return ("PASS", "")
   ```

2. Add to `logic/business-config.yaml`:
   ```yaml
   quick_rules:
     "https://bank.example.com/schemas/loan/v1.0.0":
       - rule_id: rule_005_v1
   ```

3. Restart service. No other changes needed.

---

## 9. Entity Helper System

### Problem

Validation rules that access raw JSON paths (`entity_data["financial"]["principal_amount"]`) break whenever the data model is restructured. With hundreds of rules, a field rename cascades into hundreds of code changes.

### Solution: Data Abstraction Layer

Entity helpers provide stable logical properties that map to physical JSON paths. Rules use `self.entity.principal` regardless of whether the underlying field is `amount`, `principal_amount`, or `financial.principal_amount`.

```python
# Rule code - stable across schema versions:
if self.entity.principal <= 0:
    return ("FAIL", "Principal must be positive")
```

### Version-Specific Helpers

Each major schema version has its own helper class:

**LoanV1** (schema v1.0.0) — key mappings:

| Logical Property | Physical Path |
|-----------------|---------------|
| `reference` | `loan_number` |
| `facility` | `facility_id` |
| `principal` | `financial.principal_amount` |
| `balance` | `financial.outstanding_balance` |
| `rate` | `financial.interest_rate` |
| `inception` | `dates.origination_date` |
| `maturity` | `dates.maturity_date` |
| `status` | `status` |

**LoanV2** (schema v2.0.0) — breaking changes:

| Logical Property | Physical Path (changed) |
|-----------------|------------------------|
| `reference` | `reference_number` (was `loan_number`) |
| `facility` | `facility_ref` (was `facility_id`) |
| `rate` | `financial.rate` (was `financial.interest_rate`) |
| `category` | `loan_category` (new field) |

Both helpers expose the same logical interface. Rules work unchanged across versions.

### Version Registry

The `VersionRegistry` (singleton) routes entity data to the correct helper based on the `$schema` URL declared in the data:

**Resolution order:**
1. Exact `$schema` match in `schema_to_helper_mapping`
2. Minor version fallback: `v1.2.0` → finds `v1.0.0` mapping (if enabled)
3. Default helper by entity type (when `$schema` is absent)
4. `ValueError` if no match

For schema URLs pointing to `.json` files (`file://`, `https://`), the registry fetches the schema and extracts the canonical `$id` for matching.

### Factory Function

```python
from entity_helpers import create_entity_helper

helper = create_entity_helper("loan", entity_data, track_access=True)
```

The factory delegates to `VersionRegistry.get_helper_class()`, which returns the appropriate class (`LoanV1` or `LoanV2`). The rule executor calls this automatically.

### Field Access Tracking

Helpers optionally record which properties each rule accesses during execution:

```python
helper = create_entity_helper("loan", entity_data, track_access=True)
# ... rule executes ...
dependencies = helper.get_accesses()
# [("principal", "financial.principal_amount"), ("balance", "financial.outstanding_balance")]
```

Each access is recorded as a `(logical_name, physical_path)` tuple. This powers the `discover-rules` API, enabling:
- Model change impact analysis ("which rules break if we rename this field?")
- Automated dependency documentation
- Regression testing for helper changes

### Adding a New Schema Version

1. Create `logic/models/loan.schema.v3.0.0.json`
2. Create `logic/entity_helpers/loan_v3.py` with mappings for the new schema
3. Add to `logic/business-config.yaml`:
   ```yaml
   schema_to_helper_mapping:
     "https://bank.example.com/schemas/loan/v3.0.0": "loan_v3.LoanV3"
   ```

No rule changes needed. The registry picks up the mapping on next startup.

---

## 10. Validation Workflow

### Single Entity Flow

```
Client ──POST /api/v1/validate──▶ JVM Handler
                                    │
                            1. Normalize $schema URL
                            2. get-required-data ──▶ Python Runner
                               ◀── ["parent", ...]
                            3. Fetch data from coordination service
                            4. validate ──▶ Python Runner
                               ◀── [{rule results}]
                            5. Return results to client
```

**Detailed steps:**

1. **Parse request:** Extract `entity_type`, `entity_data`, `ruleset_name`
2. **Normalize schema URL:** Convert relative `file://` URIs to absolute paths (Python's `urllib` can't resolve relative `file://` URIs). Implemented in `utils/file_io.clj`.
3. **Get required data terms:** Call Python runner's `get-required-data` with entity type, schema URL, and ruleset name. Returns vocabulary terms like `["parent"]`.
4. **Fetch external data:** Call coordination service for each vocabulary term (currently stubbed, returns empty map).
5. **Execute validation:** Call Python runner's `validate` with entity data + fetched data. Python loads rules, creates entity helper, executes hierarchically, returns results.
6. **Return results:** Hierarchical validation results with per-rule status, message, and timing.

### Batch Flow

**Inline batch** (`POST /api/v1/batch`): Accepts an array of entities with inline data. Supports mixed entity types. Calls `execute-validation` per entity, aggregates results with per-entity summaries.

**File batch** (`POST /api/v1/batch-file`): Loads entities from a URI (`file://`, `http://`, `https://`). Requires `entity_types` and `id_fields` maps to correlate schemas to types and ID fields.

Both batch endpoints pre-validate that all schemas in the batch have corresponding `id_fields` entries before processing.

---

## 11. REST API

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/validate` | Validate a single entity |
| POST | `/api/v1/batch` | Validate multiple entities (inline data) |
| POST | `/api/v1/batch-file` | Validate entities from file URI |
| POST | `/api/v1/discover-rules` | Get rule metadata and field dependencies |
| GET | `/health` | Service health check |
| GET | `/swagger-ui` | Interactive API documentation |

### Single Validation Request/Response

**Request:**
```json
{
  "entity_type": "loan",
  "entity_data": {
    "$schema": "file://../logic/models/loan.schema.v1.0.0.json",
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
      "maturity_date": "2025-12-31"
    },
    "status": "active"
  },
  "ruleset_name": "quick"
}
```

**Response:**
```json
{
  "entity_type": "loan",
  "entity_id": "LN-001",
  "results": [
    {
      "rule_id": "rule_001_v1",
      "description": "JSON Schema validation",
      "status": "PASS",
      "message": "",
      "execution_time_ms": 15.2,
      "children": []
    },
    {
      "rule_id": "rule_002_v1",
      "description": "Financial soundness checks",
      "status": "PASS",
      "message": "",
      "execution_time_ms": 1.1,
      "children": []
    }
  ],
  "summary": {
    "total_rules": 2,
    "passed": 2,
    "failed": 0,
    "not_run": 0
  }
}
```

### Batch Request

```json
{
  "entities": [
    {"entity_type": "loan", "entity_data": {"$schema": "...", ...}},
    {"entity_type": "loan", "entity_data": {"$schema": "...", ...}}
  ],
  "id_fields": {
    "file://../logic/models/loan.schema.v1.0.0.json": "loan_number"
  },
  "ruleset_name": "thorough",
  "output_mode": "response"
}
```

Supports `output_mode: "file"` with `output_path` to write results to disk instead of returning in the HTTP response.

### Batch-File Request

```json
{
  "file_uri": "file:./test/test-data/loans.json",
  "entity_types": {
    "file://../logic/models/loan.schema.v1.0.0.json": "loan"
  },
  "id_fields": {
    "file://../logic/models/loan.schema.v1.0.0.json": "loan_number"
  },
  "ruleset_name": "thorough"
}
```

### Discover Rules Request/Response

**Request:**
```json
{
  "entity_type": "loan",
  "schema_url": "file://../logic/models/loan.schema.v1.0.0.json",
  "ruleset_name": "quick"
}
```

**Response:**
```json
{
  "rule_001_v1": {
    "rule_id": "rule_001_v1",
    "entity_type": "loan",
    "description": "JSON Schema validation",
    "required_data": [],
    "field_dependencies": [["principal", "financial.principal_amount"]],
    "applicable_schemas": ["https://bank.example.com/schemas/loan/v1.0.0"]
  }
}
```

---

## 12. File Path Handling

### The Problem

Python's `urllib.request.urlopen()` cannot resolve relative `file://` URIs. A path like `file://../logic/models/schema.json` gets interpreted as `/logic/models/schema.json` from the filesystem root.

### The Solution

The JVM service normalizes all relative `file://` URIs to absolute paths before passing them to the Python runner. Implemented in `utils/file_io.clj`:

```
file://../logic/models/schema.json
  → file:///Users/.../validation-service/logic/models/schema.json

file:./test/data.json
  → file:///Users/.../jvm-service/test/data.json

https://example.com/data.json
  → https://example.com/data.json  (unchanged)
```

This normalization happens at the start of each validation workflow and is transparent to the rest of the system. It ensures the same relative paths work in both local development and Docker containers.

### Container Directory Structure

```
/app/
├── logic/               # Business-owned assets
│   ├── business-config.yaml
│   ├── models/
│   │   └── loan.schema.v1.0.0.json
│   └── rules/
│       └── loan/
├── python-runner/
│   └── local-config.yaml
└── jvm-service/         # WORKDIR
    ├── validation-service.jar
    └── test/test-data/
```

---

## 13. Data Model

### JSON Schemas

Schema files follow the naming convention `{entity_type}.schema.v{version}.json` and live in `logic/models/`. Each schema declares a canonical `$id` URL:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://bank.example.com/schemas/loan/v1.0.0",
  "title": "Loan Schema v1.0.0",
  "version": "1.0.0",
  ...
}
```

Entity data references its schema via the `$schema` field. This drives both schema validation (rule_001) and version routing (entity helper selection).

### Schema Versioning Strategy

- **Major versions** (v1 → v2): Breaking changes. Require new entity helper class. Explicit mapping in config.
- **Minor versions** (v1.0 → v1.1): Backward-compatible additions. Can fall back to major version's helper (configurable).
- **Version compatibility** is controlled in `logic/business-config.yaml` via `version_compatibility.allow_minor_version_fallback` and `strict_major_version`.

See [HOW-VERSIONING-WORKS.md](HOW-VERSIONING-WORKS.md) for a detailed versioning guide.

---

## 14. Testing

### Python Tests

| Test | Coverage |
|------|----------|
| `test_rule_executor.py` | Hierarchical execution, parent-child dependencies, error handling |
| `test_entity_helper_integration.py` | Helper injection, field access tracking, version routing |
| `test_rule_discovery.py` | Rule metadata generation, field dependency reporting |
| `test_simple_bencode.py` | Bencode message encoding/decoding |
| `test_describe.py` | Pod describe protocol response |
| `test_pod.clj` | End-to-end Clojure → Python pod communication |

### Test Data

- `tests/test_data/loan_v1_valid.json` — Valid loan conforming to v1.0.0 schema
- `tests/test_data/loan_v2_valid.json` — Valid loan conforming to v2.0.0 schema
- `jvm-service/test/test-data/loans.json` — Batch test data
- `jvm-service/test/requests/batch-*.json` — Example batch requests

### Running Tests

```bash
# Python unit tests
cd python-runner && python -m pytest tests/

# Clojure integration tests
cd jvm-service && clojure -M:test

# End-to-end pod test
cd jvm-service && bb test/babashka/run-tests.clj
```

---

## 15. Deployment

### Docker

```bash
docker build -t validation-service .
docker run -d --name validation-service -p 8080:8080 validation-service
curl http://localhost:8080/health
```

The Dockerfile packages both the JVM service and Python runner in a single image. The JVM service is the entrypoint; it spawns the Python runner as a child process.

### Local Development

```bash
# Start the JVM service (spawns Python runner automatically)
cd jvm-service && clojure -M -m validation-service.core
```

The default `library-config.edn` uses relative paths (`../python-runner/runner.py`, `../python-runner/local-config.yaml`) that work from the `jvm-service/` directory.

---

## 16. Key Design Patterns

### Transport Abstraction

Both JVM and Python abstract the communication protocol behind interfaces. Business logic has zero dependencies on specific transports. This enables:
- POC with babashka pods
- Production migration to gRPC without changing validation logic
- A/B testing of different transports
- Independent testing with mock transports

### Data Abstraction

Entity helpers isolate validation rules from the physical data model:
- Rules use stable logical properties (`loan.principal`, `loan.maturity`)
- Schema evolution handled by versioned helper classes
- Model restructuring requires updating only the helper, not the rules

### Config-Driven Rule Management

Rule sets are defined in YAML configuration, not code:
- Add/remove rules by editing config
- Reorder rule hierarchy by rearranging config
- Version-specific rules via schema URL keys
- Same rule can appear in multiple rule sets

### Convention Over Configuration

- Rule class is always named `Rule`
- Rule ID is derived from filename
- Entity type directories mirror the data model
- Schema file naming follows `{type}.schema.v{version}.json`

### Business Logic Indirection

The `logic/` directory is a layer of indirection that physically separates business-owned assets from service infrastructure. The service discovers rules, schemas, and configuration through `business_config_uri` in `local-config.yaml` — it never hardcodes paths into `logic/`. This enables:
- Business logic in a separate repository
- Independent deployment of rules without service redeployment
- Remote hosting of rules on a CDN or artifact server
- Clean ownership boundaries between service and rules teams

### Separation of Ownership

| Concern | Owner | Configuration |
|---------|-------|---------------|
| Service infrastructure | Service team | `local-config.yaml`, `library-config.edn`, `web-config.edn` |
| Rule definitions | Rules team | `logic/business-config.yaml` |
| Rule implementations | Rules team | `logic/rules/{entity_type}/*.py` |
| Entity helpers | Data model team | `logic/entity_helpers/*.py` |
| Schema definitions | Data model team | `logic/models/*.json` |

---

## 17. Production Migration Summary

The architecture is designed for straightforward migration to production:

| POC Component | Production Target | Migration Effort |
|--------------|-------------------|-----------------|
| Clojure web layer | Spring Boot controllers | Web layer rewrite |
| Clojure library layer | Java classes/interfaces | Protocol → interface, record → class |
| Babashka pods | gRPC (or retained bencode) | Transport handler swap |
| Python runner | Unchanged | None |
| Rules | Unchanged | None |
| Entity helpers | Unchanged | None |
| Two-tier config | Spring Cloud Config + CDN | URI-based (already supported) |

**Key enablers:**
- Library/web split means the two layers can be migrated independently
- Transport abstraction means protocol swap requires no business logic changes
- Python runner is entirely unchanged during JVM migration
- Two-tier config already supports remote URIs for production deployment

See [PRODUCTIONIZATION.md](PRODUCTIONIZATION.md) for the detailed migration roadmap, timeline, and decision framework.

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **Entity** | A business data object (deal, facility, or loan) |
| **Entity helper** | Python class providing stable logical properties over raw entity data |
| **Rule set** | A named collection of rules in config (e.g., "quick", "thorough") |
| **Vocabulary term** | A standardized name for external data a rule needs (e.g., "parent") |
| **Coordination service** | External service that fetches related data for validation rules |
| **Pod** | A babashka pods process — the Python runner as seen by the JVM |
| **Transport handler** | Abstract interface for JVM↔Python communication |
| **Schema URL** | The `$schema` field in entity data, used for version routing |
| **Two-tier config** | Architecture separating infrastructure config from business config |
| **Logic folder** | Directory (`logic/`) consolidating all business-owned assets — a layer of indirection enabling independent deployment |

---

**Document Version:** 1.0
**Date:** 2026-02-13
**Status:** Current — reflects completed POC
