# Python Validation Runner

Validation rule execution engine for the commercial bank loan validation service. Communicates with the JVM orchestration service via babashka pods (POC) or gRPC (production).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the runner (listens on stdin/stdout for bencode messages)
python runner.py local-config.yaml
```

The runner is normally started automatically by the JVM service, not invoked directly.

## Directory Structure

```
python-runner/
├── runner.py                    # Entry point (bootstraps logic dir, runs pod loop)
├── local-config.yaml            # Tier 1: Infrastructure config
├── requirements.txt
│
├── core/
│   ├── validation_engine.py     # Main orchestration
│   ├── rule_executor.py         # Hierarchical rule execution
│   ├── rule_loader.py           # Dynamic rule discovery and loading
│   ├── config_loader.py         # Two-tier config loading with URI support
│   ├── rule_fetcher.py          # Remote rule fetching + caching
│   └── logic_fetcher.py         # Remote logic package fetching
│
├── transport/
│   ├── base.py                  # Abstract transport interface
│   ├── pods_transport.py        # Bencode pod implementation
│   ├── bencode_reader.py        # Stream-aware bencode parser
│   └── case_conversion.py       # Kebab-case <-> snake_case conversion
│
└── tests/
    ├── test_data/               # Sample entity JSON fixtures
    ├── test_logic_fetcher.py    # Logic package fetching
    ├── test_config_loader.py    # Two-tier config loading
    ├── test_two_tier_config.py  # End-to-end config integration
    ├── test_rule_loader.py      # Rule discovery
    ├── test_rule_executor.py    # Execution engine
    ├── test_rule_fetcher.py     # Remote rule fetching
    ├── test_entity_helper_integration.py  # Helper injection
    ├── test_versioning.py       # Schema version routing
    ├── test_rule_discovery.py   # Rule metadata API
    ├── test_loan_rules.py       # End-to-end rule validation
    ├── test_discover_rules_pod.py  # discover-rules pod function
    ├── test_describe.py         # Pod describe protocol
    ├── test_simple_bencode.py   # Bencode encoding/decoding
    ├── test_e2e_bencode.py      # End-to-end bencode protocol
    ├── test_runner_startup.py   # Runner startup
    └── test_pod.clj             # Clojure pod integration test
```

Business logic assets (rules, entity helpers, schemas, business config) live in `logic/` at the project root, not here. See [../docs/TECHNICAL-DESIGN.md](../docs/TECHNICAL-DESIGN.md) Section 3 for details.

## Architecture

The Python runner follows a layered architecture:

1. **Transport Layer** (`transport/`): Handles communication protocol (bencode over stdin/stdout)
2. **Validation Engine** (`core/validation_engine.py`): Orchestrates the validation workflow
3. **Rule Executor** (`core/rule_executor.py`): Executes rules hierarchically with timing
4. **Rule Loader** (`core/rule_loader.py`): Dynamically discovers and loads rules
5. **Config Loader** (`core/config_loader.py`): Two-tier config with URI fetching and caching
6. **Logic Fetcher** (`core/logic_fetcher.py`): Resolves `logic/` directory (local or remote)
7. **Entity Helpers** (`logic/entity_helpers/`): Abstract data model from rules, with per-version classes
8. **Rules** (`logic/rules/`): Actual validation logic

### Startup Bootstrap

`runner.py` resolves the `logic/` directory before importing anything that depends on it:

1. Read `local-config.yaml` to find `business_config_uri`
2. If local path: resolve to absolute directory, add to `sys.path`
3. If remote URL: fetch entire logic package into cache, add cache to `sys.path`
4. Initialize `ValidationEngine` and enter request loop

This means switching from local development to remote logic is a single config change.

## Two-Tier Configuration

**Tier 1 — Infrastructure** (`python-runner/local-config.yaml`, service team):
```yaml
business_config_uri: "../logic/business-config.yaml"   # or https://...
logic_cache_dir: "/tmp/validation-cache"              # only used for remote URIs
```

**Tier 2 — Business logic** (`logic/business-config.yaml`, rules team):
```yaml
quick_rules:
  "https://bank.example.com/schemas/loan/v1.0.0":
    - rule_id: rule_001_v1
    - rule_id: rule_002_v1

thorough_rules:
  "https://bank.example.com/schemas/loan/v1.0.0":
    - rule_id: rule_001_v1
    - rule_id: rule_002_v1
    - rule_id: rule_003_v1
      children:
        - rule_id: rule_004_v1

schema_to_helper_mapping:
  "https://bank.example.com/schemas/loan/v1.0.0": "loan_v1.LoanV1"
  "https://bank.example.com/schemas/loan/v2.0.0": "loan_v2.LoanV2"

default_helpers:
  loan: "loan_v1.LoanV1"
```

Rules are keyed by schema URL for version-specific validation. The `$schema` field in entity data drives routing. Falls back to entity type key when `$schema` is absent.

## Writing Rules

All rules are named `Rule`, inherit from `ValidationRule`, and live in `logic/rules/{entity_type}/`:

```python
from rules.base import ValidationRule

class Rule(ValidationRule):
    def validates(self) -> str:
        return "loan"

    def required_data(self) -> list[str]:
        return []  # or ["parent", "all_siblings"]

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

The rule ID is derived from the filename (`rule_005_v1.py` -> `rule_005_v1`). The class name is always `Rule`. Access entity data through `self.entity` (injected helper), never through raw dicts.

To deploy a new rule:
1. Create `logic/rules/{entity_type}/rule_{id}_v{version}.py`
2. Add to `logic/business-config.yaml` under the appropriate rulesets
3. Restart service (or publish to remote if using remote logic)

## Running Tests

```bash
cd python-runner

# All tests
for f in tests/test_*.py; do python "$f"; done

# Individual tests
python tests/test_logic_fetcher.py       # Logic package fetching
python tests/test_config_loader.py       # Config loading
python tests/test_loan_rules.py          # End-to-end rule validation
python tests/test_versioning.py          # Schema version routing
python tests/test_rule_executor.py       # Hierarchical execution
python tests/test_e2e_bencode.py         # Full bencode protocol

# Clojure pod integration test
bb tests/test_pod.clj
```

## Documentation

- [`../docs/TECHNICAL-DESIGN.md`](../docs/TECHNICAL-DESIGN.md) - System architecture and implementation details
- [`../docs/CAPABILITIES.md`](../docs/CAPABILITIES.md) - Component responsibilities and boundaries
- [`../docs/HOW-VERSIONING-WORKS.md`](../docs/HOW-VERSIONING-WORKS.md) - Entity helper versioning
- [`../docs/PRODUCTIONIZATION.md`](../docs/PRODUCTIONIZATION.md) - Production roadmap
- [`../DESIGN-OVERVIEW.md`](../DESIGN-OVERVIEW.md) - Functional design and business context
