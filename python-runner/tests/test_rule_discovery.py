#!/usr/bin/env python3
"""Test comprehensive rule discovery API"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.validation_engine import ValidationEngine

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

LOAN_V1_DATA = {
    "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
    "id": "LOAN-DISC-001",
    "loan_number": "LN-DISC-001",
    "facility_id": "FAC-001",
    "financial": {
        "principal_amount": 100000,
        "currency": "USD",
        "interest_rate": 0.05,
        "outstanding_balance": 95000
    },
    "dates": {
        "origination_date": "2024-01-01",
        "maturity_date": "2025-01-01"
    },
    "status": "active"
}


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

    engine = ValidationEngine(CONFIG_PATH)

    print("\n=== discover_rules API Tests ===\n")

    # Test 1: Returns dict with rule metadata
    def t_returns_dict():
        result = engine.discover_rules("loan", LOAN_V1_DATA, "quick")
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert len(result) > 0, "Expected at least one rule"
    test("Returns dict with rule metadata", t_returns_dict)

    # Test 2: Each rule has required metadata fields
    def t_has_required_fields():
        result = engine.discover_rules("loan", LOAN_V1_DATA, "quick")
        required_fields = ["rule_id", "entity_type", "description", "required_data",
                          "field_dependencies", "applicable_schemas"]
        for rule_id, metadata in result.items():
            for field in required_fields:
                assert field in metadata, f"Rule {rule_id} missing field: {field}"
    test("Each rule has all required metadata fields", t_has_required_fields)

    # Test 3: rule_001_v1 metadata is correct
    def t_rule_001_metadata():
        result = engine.discover_rules("loan", LOAN_V1_DATA, "quick")
        assert "rule_001_v1" in result
        r = result["rule_001_v1"]
        assert r["rule_id"] == "rule_001_v1"
        assert r["entity_type"] == "loan"
        assert "schema" in r["description"].lower()
        assert r["required_data"] == []
        assert r["field_dependencies"] == []  # Schema rule doesn't access fields via helper
    test("rule_001_v1 metadata is correct", t_rule_001_metadata)

    # Test 4: rule_002_v1 includes field dependencies
    def t_rule_002_field_deps():
        result = engine.discover_rules("loan", LOAN_V1_DATA, "quick")
        assert "rule_002_v1" in result
        r = result["rule_002_v1"]
        assert len(r["field_dependencies"]) > 0, "rule_002_v1 should access fields"
        assert ("principal", "financial.principal_amount") in r["field_dependencies"]
    test("rule_002_v1 includes field dependencies", t_rule_002_field_deps)

    # Test 5: applicable_schemas list is present
    def t_applicable_schemas():
        result = engine.discover_rules("loan", LOAN_V1_DATA, "quick")
        for rule_id, metadata in result.items():
            assert isinstance(metadata["applicable_schemas"], list)
    test("applicable_schemas list is present for all rules", t_applicable_schemas)

    # Test 6: Works for batch mode
    def t_batch_mode():
        result = engine.discover_rules("loan", LOAN_V1_DATA, "thorough")
        assert isinstance(result, dict)
        assert len(result) > 0
    test("Works for batch mode", t_batch_mode)

    # Test 7: applicable_schemas includes correct schema URLs
    def t_applicable_schemas_urls():
        result = engine.discover_rules("loan", LOAN_V1_DATA, "quick")
        for rule_id, metadata in result.items():
            schemas = metadata["applicable_schemas"]
            # All loan rules should be applicable to v1.0.0 and v2.0.0
            assert any("v1.0.0" in s for s in schemas), f"{rule_id} should apply to v1.0.0"
            assert any("v2.0.0" in s for s in schemas), f"{rule_id} should apply to v2.0.0"
    test("applicable_schemas includes correct schema URLs", t_applicable_schemas_urls)

    print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
