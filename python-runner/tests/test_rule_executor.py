#!/usr/bin/env python3
"""Test rule_executor.py with mock rules"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add logic/ directory to sys.path for entity_helpers and rules imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logic"))

from core.rule_executor import RuleExecutor


class MockPassRule:
    """Mock rule that always passes"""
    def get_id(self):
        return "mock_pass_v1"

    def validates(self):
        return "loan"

    def required_data(self):
        return []

    def description(self):
        return "Mock rule that always passes"

    def set_required_data(self, data):
        pass

    def run(self):
        return ("PASS", "")


class MockFailRule:
    """Mock rule that always fails"""
    def get_id(self):
        return "mock_fail_v1"

    def validates(self):
        return "loan"

    def required_data(self):
        return []

    def description(self):
        return "Mock rule that always fails"

    def set_required_data(self, data):
        pass

    def run(self):
        return ("FAIL", "Mock failure message")


# Test 1: Instantiation
print("Test 1: RuleExecutor instantiation")
rules = [MockPassRule()]
entity_data = {"id": "TEST-001"}
required_data = {}
executor = RuleExecutor(rules, entity_data, required_data)
print("  ✓ RuleExecutor instantiated")

# Test 2: Execute single rule without children
print("\nTest 2: Execute single rule without children")
rule_configs = [{"rule_id": "mock_pass_v1"}]
results = executor.execute_hierarchical(rule_configs)
assert isinstance(results, list), "Results should be a list"
assert len(results) == 1, "Should have one result"
print("  ✓ Returns list of results")

# Test 3: Verify result structure
print("\nTest 3: Verify result structure")
result = results[0]
required_keys = ["rule_id", "description", "status", "message", "execution_time_ms", "children"]
for key in required_keys:
    assert key in result, f"Result missing key: {key}"
print(f"  ✓ All required keys present: {required_keys}")

# Test 4: Verify status values
print("\nTest 4: Verify status values")
assert result["status"] in ["PASS", "FAIL", "NORUN"], f"Invalid status: {result['status']}"
print(f"  ✓ Status is valid: {result['status']}")

# Test 5: Verify execution_time_ms is numeric (int or float)
print("\nTest 5: Verify execution_time_ms is numeric")
assert isinstance(result["execution_time_ms"], (int, float)), "execution_time_ms should be numeric"
print(f"  ✓ execution_time_ms is numeric: {result['execution_time_ms']}ms")

# Test 6: Verify empty children list
print("\nTest 6: Verify empty children list when no children in config")
assert result["children"] == [], "Children should be empty list"
print("  ✓ Children is empty list")

# Test 7: Hierarchical execution - parent PASS, child runs
print("\nTest 7: Hierarchical execution - parent PASS, child runs")
rules = [MockPassRule(), MockPassRule()]
rules[1].get_id = lambda: "mock_child_v1"
rules[1].description = lambda: "Mock child rule"
executor = RuleExecutor(rules, entity_data, required_data)
rule_configs = [{
    "rule_id": "mock_pass_v1",
    "children": [{"rule_id": "mock_child_v1"}]
}]
results = executor.execute_hierarchical(rule_configs)
assert len(results[0]["children"]) == 1, "Should have one child result"
assert results[0]["children"][0]["status"] == "PASS", "Child should have run and passed"
print("  ✓ Child executed when parent PASS")

# Test 8: Hierarchical execution - parent FAIL, child skipped
print("\nTest 8: Hierarchical execution - parent FAIL, children marked NORUN")
rules = [MockFailRule(), MockPassRule()]
rules[1].get_id = lambda: "mock_child_v1"
rules[1].description = lambda: "Mock child rule"
executor = RuleExecutor(rules, entity_data, required_data)
rule_configs = [{
    "rule_id": "mock_fail_v1",
    "children": [{"rule_id": "mock_child_v1"}]
}]
results = executor.execute_hierarchical(rule_configs)
assert results[0]["status"] == "FAIL", "Parent should fail"
assert len(results[0]["children"]) == 1, "Should have one child result"
assert results[0]["children"][0]["status"] == "NORUN", "Child should be marked NORUN"
assert "Parent rule did not pass" in results[0]["children"][0]["message"], "Should have skip message"
print("  ✓ Children marked NORUN when parent FAIL")

print("\n" + "="*50)
print("✓ All tests passed!")
print("="*50)
