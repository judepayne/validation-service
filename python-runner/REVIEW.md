# Python Runner - Code Review Guide

This document lists all Python files in dependency order (inside-out). Start with files that depend on nothing, then review files that depend on those, and so on.

---

## Review Order: Core Implementation

### Layer 1: Utilities & Base Classes (No Dependencies) - DONE

#### 1. `transport/case_conversion.py`
Utility functions for converting between kebab-case (Clojure) and snake_case (Python). Handles bidirectional conversion for pod protocol communication.

#### 2. `transport/bencode_reader.py`
Stream-aware bencode parser for babashka pods protocol. Reads bencode-encoded messages from stdin, handling partial reads and buffering correctly.

#### 3. `transport/base.py`
Abstract base class defining the transport protocol interface (`TransportHandler`). Declares methods for starting, receiving requests, sending responses, and handling errors - enables swapping bencode for gRPC.

#### 4. `rules/base.py`
Abstract base class for validation rules (`ValidationRule`). Accepts rule ID via constructor injection and provides `get_id()` implementation. Rules must implement 5 abstract methods: `validates()`, `required_data()`, `description()`, `set_required_data()`, and `run()`. The rule ID is automatically derived from the filename by the rule loader.

---

### Layer 2: Entity Helpers (Depend on Base/Utils) - DONE

#### 5. `entity_helpers/loan_v1.py`
Entity helper for loan schema v1.0.0. Provides logical property accessors (e.g., `principal`, `rate`, `inception`) that abstract physical JSON paths, with optional field access tracking for dependency analysis.

#### 6. `entity_helpers/loan_v2.py`
Entity helper for loan schema v2.0.0. Mirrors v1 structure but maps to v2 schema fields (e.g., `reference_number` instead of `loan_number`, `facility_ref` instead of `facility_id`).

#### 7. *[Removed - consolidated to loan_v1.py]*
Previously: Backward-compatibility module. Now removed - all code uses explicit versioned classes (LoanV1, LoanV2).

#### 8. `entity_helpers/version_registry.py`
Schema version routing system. Loads `config.yaml` mappings of schema URLs to helper classes, provides `get_helper_class(schema_url, entity_type)` to route entity data to correct versioned helper.

#### 9. `entity_helpers/__init__.py`
Package initialization and factory function. Exports `create_entity_helper(entity_type, entity_data, track_access)` which uses `VersionRegistry` to instantiate the correct helper class based on `$schema` field.

---

### Layer 3: Rules (Depend on Base + Helpers) - DONE

#### 10. `rules/loan/rule_001_v1.py`
JSON schema validation rule. Fetches schema from `$schema` URL (file:// or https://) and validates entity data against it using `jsonschema` library - returns PASS/FAIL/NORUN based on schema conformance.

#### 11. `rules/loan/rule_002_v1.py`
Business logic validation for loan financial soundness. Checks: positive principal, non-negative interest rate, maturity after origination, outstanding balance ≤ principal - accesses entity via helper properties.

---

### Layer 4: Core Validation Logic (Depends on Rules + Helpers)

#### 12. `core/rule_loader.py`
Dynamic rule discovery and loading. Scans `rules/` directory for Python files matching `rule_<id>_v<version>.py` pattern, dynamically imports them, and instantiates rule classes with injected IDs. Uses filename as single source of truth - all rules use standard class name `Rule`, with ID derived from filename (e.g., `rule_001_v1.py` → rule ID `rule_001_v1`). Eliminates name derivation coupling and enables zero-registration rule system.

#### 13. `core/rule_executor.py`
Hierarchical rule execution engine. Injects entity helpers into rules, executes rules in dependency order (parents before children), measures execution time, captures PASS/FAIL/ERROR/NORUN status, and builds hierarchical result tree.

#### 14. `core/validation_engine.py`
Core validation orchestration (transport-agnostic). Implements three operations: `get_required_data()` (introspect rules for vocabulary needs), `validate()` (execute rules and return results), and `discover_rules()` (comprehensive rule metadata API).

#### 15. `core/__init__.py`
Empty package marker for `core/` module.

---

### Layer 5: Transport Layer (Depends on Core + Utilities) - DONE

#### 16. `transport/pods_transport.py`
Babashka pods protocol implementation. Handles `describe`, `invoke`, and `shutdown` operations, reads bencode requests from stdin, sends bencode responses to stdout, performs kebab↔snake case conversion.

#### 17. `transport/__init__.py`
Empty package marker for `transport/` module.

---

### Layer 6: Main Entry Point (Depends on Everything)

#### 18. `runner.py`
Main entry point and pod lifecycle manager. Initializes `ValidationEngine` with config, creates `PodsTransportHandler`, enters request loop dispatching to engine methods (`get_required_data`, `validate`, `discover_rules`), handles graceful shutdown.

---

## Review Order: Tests

### Layer 7: Unit Tests (Test Individual Components)

#### 19. `tests/test_simple_bencode.py`
Unit tests for bencode encoding/decoding. Verifies bencode format correctness for integers, strings, lists, dicts, and nested structures.

#### 20. `tests/test_rule_loader.py`
Unit tests for dynamic rule loading. Verifies `RuleLoader` correctly discovers rule files, instantiates classes, validates interface conformance, and handles missing rules.

#### 21. `tests/test_rule_executor.py`
Unit tests for rule execution engine. Tests hierarchical execution, parent-before-children ordering, timing capture, error handling (PASS/FAIL/ERROR/NORUN), and result structure.

#### 22. `tests/test_versioning.py`
Unit tests for schema version routing. Verifies `VersionRegistry` correctly maps schema URLs to helper classes, v1 and v2 schemas validate correctly against their respective data formats, and schema mismatches are detected.

#### 23. `tests/test_rule_discovery.py`
Unit tests for comprehensive rule metadata API. Tests `discover_rules()` returns complete metadata (rule_id, entity_type, description, required_data, field_dependencies, applicable_schemas) for all rules in given mode/schema.

---

### Layer 8: Integration Tests (Test Component Interactions)

#### 24. `tests/test_entity_helper_integration.py`
Integration test for entity helper injection into rules. Verifies `RuleExecutor` correctly creates helpers, injects into rule instances, and rules can access entity properties through helper interface.

#### 25. `tests/test_loan_rules.py`
Integration test for loan validation rules end-to-end. Tests both `rule_001_v1` (schema validation) and `rule_002_v1` (business logic) against valid and invalid loan data, verifies correct PASS/FAIL status and error messages.

#### 26. `tests/test_describe.py`
Integration test for pod describe operation. Verifies `runner.py` responds to describe request with correct namespace, function names (`get-required-data`, `validate`, `discover-rules`), and shutdown op.

---

### Layer 9: End-to-End Tests (Test Complete System)

#### 27. `tests/test_e2e_bencode.py`
E2E test of bencode protocol. Spawns runner process, sends bencode-encoded requests (get_required_data, validate with valid/invalid data, unknown function), verifies bencode responses match expected format and content.

#### 28. `tests/test_runner_startup.py`
E2E test of runner startup and shutdown. Verifies runner process starts without errors, listens on stdin, responds to describe, and terminates cleanly on shutdown command.

#### 29. `tests/test_discover_rules_pod.py`
Manual E2E test demonstrating `discover-rules` pod function. Shows comprehensive metadata output (rule_id, description, field_dependencies, applicable_schemas) in human-readable format - useful for understanding API.

---

### Layer 10: Test Utilities

#### 30. `run_all_tests.py`
Test orchestration script. Runs all Python test files in sequence, reports pass/fail status for each, and generates summary - ensures full test suite passes before deployment.

---

## Review Strategy

**For each file:**
1. **Understand its purpose** - Read the 1-3 sentence summary first
2. **Check dependencies** - Files listed earlier should already be understood
3. **Review the interface** - What does it expose? (classes, functions, constants)
4. **Review the implementation** - Does it match the architecture? Are there edge cases?
5. **Check error handling** - Are exceptions handled appropriately?
6. **Verify tests exist** - Is this component tested? (see test files)

**Focus areas:**
- **Abstraction boundaries** - Do entity helpers hide physical schema details?
- **Version routing** - Does `VersionRegistry` correctly dispatch to v1/v2?
- **Rule interface** - Do rules follow the 6-method contract?
- **Transport abstraction** - Is business logic independent of pods protocol?
- **Error handling** - Are errors categorized correctly (validation vs. system)?

**Expected time:**
- **Core implementation** (files 1-18): ~3-4 hours
- **Tests** (files 19-31): ~2-3 hours
- **Total**: ~5-7 hours for thorough review

---

## Post-Review Checklist

- [ ] All base classes/interfaces are well-defined
- [ ] Entity helpers properly abstract physical schema
- [ ] Version routing works for both v1 and v2
- [ ] Rules follow the ValidationRule interface
- [ ] Core validation logic is transport-agnostic
- [ ] Transport layer correctly implements pods protocol
- [ ] All 12 test suites pass
- [ ] No hard-coded paths (use config.yaml)
- [ ] Error messages are informative
- [ ] Code follows project conventions (snake_case, type hints, docstrings)

---

**Document Version:** 1.0
**Last Updated:** 2026-02-09
**Total Files:** 31 (18 implementation, 13 tests)
