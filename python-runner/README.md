# Python Validation Runner

Babashka pods-based validation rule execution engine for the commercial bank loan validation service.

## Project Status: Proof of Concept (POC)

This is a **Phase 1 POC implementation** designed to validate the architecture and rule execution approach. The Python runner is production-ready, but the overall system architecture will evolve:

**Current (POC - Phase 1):**
- JVM Service: Clojure
- Communication: Babashka pods (bencode protocol over stdin/stdout)
- Python Runner: ✅ Complete (this component)

**Production (Phase 2):**
- JVM Service: Java (Spring Boot) - **Migration assisted by AI**
- Communication: gRPC - **Migration assisted by AI**
- Python Runner: Unchanged (same code, different transport layer)

The Python runner's **transport abstraction layer** (`transport/base.py`) enables seamless migration from pods to gRPC without changing validation logic. AI tools will assist in migrating the JVM orchestration service from Clojure to Java and implementing the gRPC transport.

**See:**
- [`../docs/POD-VS-GRPC.md`](../docs/POD-VS-GRPC.md) - Detailed comparison of protocols and why gRPC for production
- [`../docs/PRODUCTIONIZATION.md`](../docs/PRODUCTIONIZATION.md) - Complete production roadmap and migration strategy (Section 8: JVM Service Migration)

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Running as Babashka Pod

```bash
# Start the runner (listens on stdin/stdout for bencode messages)
python runner.py config.yaml
```

### Running Tests

```bash
# Run all Python tests (from python-runner/)
python tests/test_rule_loader.py
python tests/test_rule_executor.py
python tests/test_entity_helper_integration.py
python tests/test_versioning.py
python tests/test_field_dependencies.py
python tests/test_rule_discovery.py
python tests/test_loan_rules.py
python tests/test_describe.py
python tests/test_simple_bencode.py
python tests/test_e2e_bencode.py
python tests/test_runner_startup.py

# Full end-to-end pod protocol test
bb tests/test_pod.clj
```

## Directory Structure

```
python-runner/
├── runner.py                   # Main entry point (babashka pod protocol)
├── config.yaml                 # Rule configuration
│
├── core/                       # Validation logic package
│   ├── validation_engine.py    # Core validation orchestration
│   ├── rule_executor.py        # Hierarchical rule execution
│   └── rule_loader.py          # Dynamic rule discovery and loading
│
├── transport/                  # Communication layer abstraction
│   ├── base.py                 # Abstract transport interface
│   ├── pods_transport.py       # Bencode pod implementation
│   ├── bencode_reader.py       # Stream-aware bencode parser
│   └── case_conversion.py      # Kebab ↔ snake case conversion
│
├── entity_helpers/             # Domain model abstraction
│   ├── __init__.py             # Factory function + exports
│   ├── loan_v1.py              # Loan schema v1.0.0 helper
│   ├── loan_v2.py              # Loan schema v2.0.0 helper
│   └── version_registry.py     # Schema URL → helper class routing
│
├── rules/                      # Validation rule implementations
│   └── loan/
│       ├── rule_001_v1.py      # JSON schema validation
│       └── rule_002_v1.py      # Business logic checks
│
└── tests/                      # All tests
    ├── test_data/              # Sample entity JSON fixtures
    ├── test_rule_loader.py
    ├── test_rule_executor.py
    ├── test_entity_helper_integration.py
    ├── test_versioning.py
    ├── test_field_dependencies.py
    ├── test_loan_rules.py
    ├── test_describe.py
    ├── test_simple_bencode.py
    ├── test_e2e_bencode.py
    ├── test_runner_startup.py
    └── test_pod.clj
```

## Architecture

The Python runner follows a layered architecture:

1. **Transport Layer** (`transport/`): Handles communication protocol (bencode over stdin/stdout)
2. **Validation Engine** (`core/validation_engine.py`): Orchestrates the validation workflow
3. **Rule Executor** (`core/rule_executor.py`): Executes rules hierarchically with timing
4. **Rule Loader** (`core/rule_loader.py`): Dynamically discovers and loads rules
5. **Entity Helpers** (`entity_helpers/`): Abstract data model from rules, with per-version classes
6. **Rules** (`rules/`): Actual validation logic

### Key Design Principles

- **Transport Abstraction**: Can swap bencode for gRPC without changing business logic
- **Entity Helper Abstraction**: Rules use domain properties (`loan.principal`) not physical paths (`data['financial']['principal_amount']`)
- **Hierarchical Execution**: Parent rules run before children, dependency-aware
- **Dynamic Loading**: Rules discovered from filesystem, no manual registration

## Configuration

The Python runner is **rule-set agnostic** - it executes named rule sets without understanding their semantic purpose. The JVM orchestration service controls when validation occurs (inline/batch mode) and which rule set to execute.

### Architecture: Separation of Concerns

```
JVM Service (Orchestration)          Python Runner (Execution)
------------------------             ------------------------
- Inline mode (real-time)      →     - Receives ruleset_name
- Batch mode (background)      →     - Executes named rule set
- Decides when to validate           - Returns results
- Chooses which rule set
```

The JVM service might map:
- Inline mode → `ruleset_name: "quick"` (minimal checks)
- Batch mode → `ruleset_name: "thorough"` (comprehensive checks)

But these mappings are JVM service decisions, not Python runner concerns.

### Rule Set Configuration

Edit `config.yaml` to define named rule sets:

```yaml
quick_rules:
  loan:
    - rule_id: rule_001_v1  # Essential checks only
    - rule_id: rule_002_v1

thorough_rules:
  loan:
    - rule_id: rule_001_v1  # All checks
    - rule_id: rule_002_v1
    - rule_id: rule_055_v1
    - rule_id: rule_100_v1

# You can define any named rule sets
audit_rules:
  loan:
    - rule_id: rule_001_v1
    - rule_id: rule_audit_v1
```

### Version-Based Rule Loading

Rules are assigned per schema version to enable different validation rules for different entity versions:

```yaml
quick_rules:
  "https://bank.example.com/schemas/loan/v1.0.0":
    - rule_id: rule_001_v1
    - rule_id: rule_002_v1
  "https://bank.example.com/schemas/loan/v2.0.0":
    - rule_id: rule_001_v2
    - rule_id: rule_002_v2
  # Backward compatibility fallback
  loan:
    - rule_id: rule_001_v1
```

The `$schema` field in entity data determines which rules apply:

```json
{
  "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
  "id": "LOAN-12345",
  ...
}
```

When `get_required_data()` or `validate()` is called, the engine:
1. Receives `ruleset_name` parameter (e.g., "quick", "thorough", "audit")
2. Extracts the `schema_url` from the entity's `$schema` field
3. Looks up rules by `schema_url` within the specified rule set
4. Falls back to `entity_type` if no schema-specific rules are found

This enables seamless evolution of data models - v1 and v2 loans can coexist with different validation rules.

## Writing Rules

All rule classes must be named `Rule` and inherit from `ValidationRule`. The rule ID is automatically derived from the filename and injected by the rule loader.

Rules must implement 5 methods (get_id is inherited from base class):

```python
from rules.base import ValidationRule

class Rule(ValidationRule):
    """
    All rules use the standard class name 'Rule'.
    The rule ID is injected at instantiation from the filename.
    """

    def validates(self) -> str:
        """Return entity type this rule validates."""
        return "loan"

    def required_data(self) -> list[str]:
        """Return list of required data vocabulary terms."""
        return []  # or ["parent", "all_siblings"]

    def description(self) -> str:
        """Return plain English description of rule."""
        return "Entity data must conform to its declared JSON schema"

    def set_required_data(self, data: dict) -> None:
        """Receive required data before execution."""
        pass  # Store data in instance variables

    def run(self) -> tuple[str, str]:
        """Execute validation, return (status, message).

        Status values:
        - PASS: Validation succeeded
        - FAIL: Validation failed (invalid data)
        - NORUN: Rule could not execute (missing dependencies)

        Note: If run() raises an exception, the executor will catch it
        and return ERROR status with the exception details.
        """
        # Access entity via self.entity (injected by rule executor)
        # The rule ID is available via self.get_id()
        if self.entity.principal > 0:
            return ("PASS", "")
        return ("FAIL", "Principal must be positive")
```

**Key Design Principle:** The filename is the single source of truth for rule identity. A file named `rule_001_v1.py` automatically becomes rule ID `rule_001_v1`. This eliminates naming mismatches and ensures the ID, filename, and class are always in sync.

### Using Entity Helpers

Access entity data through the injected helper (never access `entity_data` dict directly):

```python
# ✅ Good - uses logical domain properties
principal = self.entity.principal
rate = self.entity.rate
inception = self.entity.inception

# ❌ Bad - tightly coupled to physical model structure
principal = self.entity_data['financial']['principal_amount']
```

**Why?** The model structure can change, but helper properties remain stable.

### Fetching Schemas from URIs

Rules that need to validate against JSON schemas can fetch them directly using Python's built-in `urllib.request`:

```python
import urllib.request
import json

# Entity data contains $schema field with fetchable URI
schema_url = entity_data.get("$schema")

# Fetch schema (works for both file:// and https:// URIs)
try:
    with urllib.request.urlopen(schema_url, timeout=10) as response:
        schema = json.loads(response.read())
except Exception as e:
    return ("NORUN", f"Failed to fetch schema from {schema_url}: {str(e)}")
```

**POC**: Entity data uses `file://` URIs pointing to local schema files
**Production**: Entity data uses `https://` URIs pointing to schema server

Example:
```json
{
  "$schema": "file:///absolute/path/to/models/loan.schema.v1.0.0.json",
  "id": "LOAN-12345",
  ...
}
```

### Rule File Naming

- **File**: `rules/<entity_type>/rule_<id>_v<version>.py`
- **Class**: Always `Rule` (standard name for all rules)

Example:
- File: `rules/loan/rule_001_v1.py`
- Class: `Rule`
- Rule ID: `rule_001_v1` (automatically derived from filename)

## Babashka Pod Protocol

The runner implements the babashka pods protocol:

### Operations

1. **describe**: Returns pod metadata (namespaces, functions, ops)
2. **invoke**: Executes a function:
   - `get-required-data`: Returns list of external data vocabulary terms needed
   - `validate`: Executes validation rules and returns results
   - `discover-rules`: Returns comprehensive metadata about all applicable rules
3. **shutdown**: Graceful shutdown

### Communication

- **Protocol**: Bencode over stdin/stdout
- **Format**: JSON (responses are JSON-encoded then bencode-wrapped)
- **Functions**: `get-required-data`, `validate`, `discover-rules`

### Example Usage from Clojure (JVM Service)

**Note:** The JVM service has its own inline/batch mode for orchestration. It passes a `ruleset_name` to the Python runner to specify which rule set to execute. These are independent concerns.

```clojure
(require '[babashka.pods :as pods])

;; Load pod
(pods/load-pod ["python3" "runner.py" "config.yaml"])

;; JVM Service Example: Inline mode (real-time) uses "quick" rule set
(pods/invoke "pod.validation-runner" 'validate
  {:entity_type "loan"
   :entity_data {:$schema "https://bank.example.com/schemas/loan/v1.0.0"
                 :id "LOAN-12345"
                 :financial {:principal_amount 100000}}
   :ruleset_name "quick"      ; ← JVM service specifies which rule set
   :required_data {}})

;; Returns: [{:rule_id "rule_001_v1" :status "PASS" :message ""}]

;; JVM Service Example: Batch mode (background) uses "thorough" rule set
(pods/invoke "pod.validation-runner" 'validate
  {:entity_type "loan"
   :entity_data {:$schema "https://bank.example.com/schemas/loan/v1.0.0" ...}
   :ruleset_name "thorough"   ; ← More comprehensive rule set
   :required_data {}})

;; Discover all rules and their metadata for a specific rule set
(pods/invoke "pod.validation-runner" 'discover-rules
  {:entity_type "loan"
   :entity_data {:$schema "https://bank.example.com/schemas/loan/v1.0.0" ...}
   :ruleset_name "quick"})

;; Returns: {"rule_001_v1" {:rule_id "rule_001_v1"
;;                          :entity_type "loan"
;;                          :description "Entity data must conform to its declared JSON schema"
;;                          :required_data []
;;                          :field_dependencies []
;;                          :applicable_schemas ["https://bank.example.com/schemas/loan/v1.0.0"
;;                                               "https://bank.example.com/schemas/loan/v2.0.0"]}
;;           "rule_002_v1" {:rule_id "rule_002_v1"
;;                          :entity_type "loan"
;;                          :description "Loan must have positive principal..."
;;                          :required_data []
;;                          :field_dependencies [["principal" "financial.principal_amount"]
;;                                               ["inception" "dates.origination_date"] ...]
;;                          :applicable_schemas ["https://bank.example.com/schemas/loan/v1.0.0"
;;                                               "https://bank.example.com/schemas/loan/v2.0.0"]}}
```

### Rule Discovery API

The `discover-rules` function provides comprehensive metadata about all rules applicable to an entity. This is the foundation for rule governance, documentation generation, and impact analysis.

**Use Cases:**
- **Documentation Generation**: Auto-generate rule docs from metadata
- **Impact Analysis**: Identify which rules use which fields
- **Rule Governance**: Browse all rules by entity type, schema version, or mode
- **Testing**: Verify rule configuration and coverage

**Example:**

```clojure
(def rules-metadata
  (pods/invoke "pod.validation-runner" 'discover-rules
    {:entity_type "loan"
     :entity_data {:$schema "https://bank.example.com/schemas/loan/v1.0.0"
                   :id "LOAN-001"
                   :financial {:principal_amount 100000}
                   :dates {:origination_date "2024-01-01"
                          :maturity_date "2025-01-01"}}
     :mode "inline"}))

;; Metadata for each rule includes:
;; - rule_id: Unique identifier
;; - entity_type: What entity this validates ("loan", "facility", etc.)
;; - description: Plain English business purpose
;; - required_data: External data vocabulary terms needed (e.g., ["parent", "siblings"])
;; - field_dependencies: Which entity helper properties are accessed
;; - applicable_schemas: Which schema versions include this rule
```

**Field Dependencies Format:**

Each field dependency is a `[logical_name, physical_path]` tuple:
- `logical_name`: The domain property name used in rules (e.g., `"principal"`)
- `physical_path`: The actual path in entity data (e.g., `"financial.principal_amount"`)

This mapping shows how the entity helper abstracts physical data structure from rule logic.
```

## Testing

### Unit Tests

```bash
python tests/test_rule_loader.py                 # Rule discovery
python tests/test_rule_executor.py               # Execution engine
python tests/test_entity_helper_integration.py   # Helper injection
python tests/test_versioning.py                  # Schema version routing
python tests/test_field_dependencies.py          # Field dependency introspection
python tests/test_rule_discovery.py              # Comprehensive rule metadata API
python tests/test_loan_rules.py                  # End-to-end rule validation
```

### Integration Tests

```bash
bb tests/test_pod.clj  # Full end-to-end pod protocol test
```

## Documentation

See parent directory for comprehensive design documentation:

- `../DESIGN.md` - Functional design and business context
- `../TECHNICAL-DESIGN.md` - Architecture and implementation details
- `../docs/CAPABILITIES.md` - Component responsibilities and boundaries
- `../docs/HOW-VERSIONING-WORKS.md` - Multi-version schema support
- `../docs/PRODUCTIONIZATION.md` - Production roadmap and requirements

## Development

### Adding a New Rule

1. Create file: `rules/<entity>/rule_<id>_v<version>.py`
2. Implement 5 required methods (get_id is inherited)
3. Add to `config.yaml` under appropriate rule sets (e.g., `quick_rules`, `thorough_rules`)
4. Write tests
5. Test with: `bb tests/test_pod.clj`

### Adding a New Rule Set

1. Add new section to `config.yaml`:
   ```yaml
   audit_rules:
     loan:
       - rule_id: rule_001_v1
       - rule_id: rule_audit_v1
   ```
2. JVM service passes `ruleset_name: "audit"` when calling pod functions

### Adding a New Entity Type

1. Create helper: `entity_helpers/<entity>_v1.py` (see `loan_v1.py` as template)
2. Add schema mapping to `config.yaml` under `schema_to_helper_mapping`
3. Create rules directory: `rules/<entity>/`
4. Add entity to rule sets in `config.yaml`

## Troubleshooting

### Pod hangs when loading

- Check that `runner.py` is executable: `chmod +x runner.py`
- Verify Python path: `which python3`
- Check for syntax errors: `python3 -m py_compile runner.py`

### Rule not found

- Verify rule file naming matches pattern: `rule_<id>_v<version>.py`
- Check class name matches: `Rule<id>V<version>`
- Ensure rule is registered in `config.yaml`

### Entity helper property not found

- Use logical property names (e.g., `loan.principal` not `loan.principal_amount`)
- Check `entity_helpers/loan_v1.py` for available properties
- Verify entity type matches rule's `validates()` return value

## License

Internal bank project - not for public distribution.

## Implementation Status

**Phase 1 POC: COMPLETE** ✅ (2026-02-07)
- ✅ All 10 implementation phases complete
- ✅ Babashka pod protocol fully working
- ✅ Transport abstraction layer ready for gRPC migration
- ✅ Two example rules implemented (schema validation + business logic)
- ✅ End-to-end tests passing

**Current Work:**
- JVM Service (Clojure) - Phase 1 POC orchestration service

**Future Work (Phase 2):**
- AI-assisted migration: Clojure → Java
- AI-assisted migration: Babashka pods → gRPC transport
- Production features (see [`../docs/PRODUCTIONIZATION.md`](../docs/PRODUCTIONIZATION.md))

**Key Design Principle:**
The Python runner's architecture is **migration-ready**. The transport abstraction layer allows switching from babashka pods to gRPC by implementing a new `GrpcTransportHandler` - no changes to validation engine, rules, or entity helpers required.
