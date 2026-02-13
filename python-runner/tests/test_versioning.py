"""
Tests for entity helper versioning system.

Verifies that schema URL → helper class routing works correctly,
and that v1/v2 loan data is validated against the correct schema.
"""

import sys
import os
import json

# Add python-runner to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add parent directory to sys.path for rules imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from entity_helpers.version_registry import VersionRegistry, get_registry, reset_registry
from entity_helpers.loan_v1 import LoanV1
from entity_helpers.loan_v2 import LoanV2


CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "local-config.yaml")


def load_test_data(filename):
    path = os.path.join(os.path.dirname(__file__), "test_data", filename)
    with open(path) as f:
        return json.load(f)


def run_tests():
    passed = 0
    failed = 0

    def test(name, fn):
        nonlocal passed, failed
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1

    print("\n=== VersionRegistry Tests ===\n")

    # --- Test 1: Registry reads config mapping ---
    def t_reads_config():
        reset_registry()
        registry = VersionRegistry(CONFIG_PATH)
        assert "https://bank.example.com/schemas/loan/v1.0.0" in registry._schema_map
        assert "https://bank.example.com/schemas/loan/v2.0.0" in registry._schema_map
        assert registry._schema_map["https://bank.example.com/schemas/loan/v1.0.0"] == "loan_v1.LoanV1"
        assert registry._schema_map["https://bank.example.com/schemas/loan/v2.0.0"] == "loan_v2.LoanV2"
    test("VersionRegistry reads config mapping correctly", t_reads_config)

    # --- Test 2: Schema URL parsing ---
    def t_parse_url():
        reset_registry()
        registry = VersionRegistry(CONFIG_PATH)
        entity_type, version, major = registry.parse_schema_url(
            "https://bank.example.com/schemas/loan/v1.0.0"
        )
        assert entity_type == "loan", f"Expected 'loan', got '{entity_type}'"
        assert version == "1.0.0", f"Expected '1.0.0', got '{version}'"
        assert major == "1", f"Expected '1', got '{major}'"
    test("Schema URL parsing (loan, 1.0.0, major=1)", t_parse_url)

    # --- Test 3: v1 entity_data loads LoanV1 ---
    def t_v1_loads_loan_v1():
        reset_registry()
        registry = VersionRegistry(CONFIG_PATH)
        v1_data = load_test_data("loan_v1_valid.json")
        helper_class = registry.get_helper_class(v1_data, "loan")
        assert helper_class is LoanV1, f"Expected LoanV1, got {helper_class}"
    test("v1 entity_data loads LoanV1 helper", t_v1_loads_loan_v1)

    # --- Test 4: v2 entity_data loads LoanV2 ---
    def t_v2_loads_loan_v2():
        reset_registry()
        registry = VersionRegistry(CONFIG_PATH)
        v2_data = load_test_data("loan_v2_valid.json")
        helper_class = registry.get_helper_class(v2_data, "loan")
        assert helper_class is LoanV2, f"Expected LoanV2, got {helper_class}"
    test("v2 entity_data loads LoanV2 helper", t_v2_loads_loan_v2)

    # --- Test 5: Missing $schema uses default helper (LoanV1) ---
    def t_missing_schema_uses_default():
        reset_registry()
        registry = VersionRegistry(CONFIG_PATH)
        data_no_schema = {"id": "LOAN-99999", "status": "active"}
        helper_class = registry.get_helper_class(data_no_schema, "loan")
        assert helper_class is LoanV1, f"Expected LoanV1 (default helper), got {helper_class}"
    test("Missing $schema uses default helper (LoanV1)", t_missing_schema_uses_default)

    # --- Test 6: Minor version fallback (v1.1.0 → v1.0.0 helper) ---
    def t_minor_version_fallback():
        reset_registry()
        registry = VersionRegistry(CONFIG_PATH)
        data_v1_1 = {"$schema": "https://bank.example.com/schemas/loan/v1.1.0"}
        helper_class = registry.get_helper_class(data_v1_1, "loan")
        # v1.1.0 falls back to v1.0.0 which maps to loan_v1.LoanV1
        assert helper_class is LoanV1, f"Expected LoanV1 (v1.1.0 falls back to v1.0.0), got {helper_class}"
    test("Minor version fallback (v1.1.0 → v1.0.0 helper)", t_minor_version_fallback)

    # --- Test 7: Unknown major version raises ValueError ---
    def t_unknown_major_raises():
        reset_registry()
        registry = VersionRegistry(CONFIG_PATH)
        data_v9 = {"$schema": "https://bank.example.com/schemas/loan/v9.0.0"}
        try:
            registry.get_helper_class(data_v9, "loan")
            raise AssertionError("Should have raised ValueError")
        except ValueError:
            pass  # expected
    test("Unknown major version raises ValueError", t_unknown_major_raises)

    print("\n=== LoanV2 Field Mapping Tests ===\n")

    # --- Test 8: LoanV2.rate reads from financial.rate ---
    def t_v2_rate_mapping():
        v2_data = load_test_data("loan_v2_valid.json")
        helper = LoanV2(v2_data)
        assert helper.rate == 0.05, f"Expected 0.05, got {helper.rate}"
    test("LoanV2.rate reads from financial.rate", t_v2_rate_mapping)

    # --- Test 9: LoanV2.reference reads from reference_number ---
    def t_v2_reference_mapping():
        v2_data = load_test_data("loan_v2_valid.json")
        helper = LoanV2(v2_data)
        assert helper.reference == "LN-2024-00002", f"Expected 'LN-2024-00002', got {helper.reference}"
    test("LoanV2.reference reads from reference_number", t_v2_reference_mapping)

    # --- Test 10: LoanV2.facility reads from facility_ref ---
    def t_v2_facility_mapping():
        v2_data = load_test_data("loan_v2_valid.json")
        helper = LoanV2(v2_data)
        assert helper.facility == "FAC-200", f"Expected 'FAC-200', got {helper.facility}"
    test("LoanV2.facility reads from facility_ref", t_v2_facility_mapping)

    # --- Test 11: LoanV2.category reads from loan_category ---
    def t_v2_category_mapping():
        v2_data = load_test_data("loan_v2_valid.json")
        helper = LoanV2(v2_data)
        assert helper.category == "commercial", f"Expected 'commercial', got {helper.category}"
    test("LoanV2.category reads from loan_category", t_v2_category_mapping)

    print("\n=== Schema Validation Cross-Version Tests ===\n")

    # --- Test 12: v2 loan data fails rule_001_v1 when validated against v1 schema ---
    def t_v2_fails_v1_schema():
        from rules.loan.rule_001_v1 import Rule
        from entity_helpers.loan_v2 import LoanV2

        v2_data = load_test_data("loan_v2_valid.json")
        # Override schema to claim it's v1 to test cross-version failure
        v2_data_claiming_v1 = dict(v2_data)
        v2_data_claiming_v1["$schema"] = "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"

        rule = Rule("rule_001_v1")
        rule.entity = LoanV1(v2_data_claiming_v1)
        rule.entity._data = v2_data_claiming_v1
        status, message = rule.run()
        assert status == "FAIL", f"Expected FAIL (v2 data vs v1 schema), got {status}: {message}"
    test("v2 loan data fails rule_001_v1 when validated against v1 schema", t_v2_fails_v1_schema)

    # --- Test 13: v2 loan data passes rule_001_v1 when validated against v2 schema ---
    def t_v2_passes_v2_schema():
        from rules.loan.rule_001_v1 import Rule

        v2_data = load_test_data("loan_v2_valid.json")

        rule = Rule("rule_001_v1")
        rule.entity = LoanV2(v2_data)
        rule.entity._data = v2_data
        status, message = rule.run()
        assert status == "PASS", f"Expected PASS (v2 data vs v2 schema), got {status}: {message}"
    test("v2 loan data passes rule_001_v1 when validated against v2 schema", t_v2_passes_v2_schema)

    # --- Test 14: v1 loan data passes rule_001_v1 against v1 schema ---
    def t_v1_passes_v1_schema():
        from rules.loan.rule_001_v1 import Rule

        v1_data = load_test_data("loan_v1_valid.json")

        rule = Rule("rule_001_v1")
        rule.entity = LoanV1(v1_data)
        rule.entity._data = v1_data
        status, message = rule.run()
        assert status == "PASS", f"Expected PASS (v1 data vs v1 schema), got {status}: {message}"
    test("v1 loan data passes rule_001_v1 against v1 schema", t_v1_passes_v1_schema)

    print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
