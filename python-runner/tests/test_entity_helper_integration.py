#!/usr/bin/env python3
"""Test entity helper integration in rule_executor.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logic"))

from core.rule_executor import RuleExecutor
from entity_helpers import LoanV1


class MockLoanRule:
    """Mock rule that accesses entity helper"""
    def get_id(self):
        return "mock_loan_rule_v1"

    def validates(self):
        return "loan"

    def required_data(self):
        return []

    def description(self):
        return "Mock loan rule that uses entity helper"

    def set_required_data(self, data):
        pass

    def run(self):
        # Access entity helper (should be injected)
        if not hasattr(self, 'entity'):
            return ("FAIL", "Entity helper not injected")

        # Access loan properties through helper
        try:
            principal = self.entity.principal
            currency = self.entity.currency
            return ("PASS", f"Accessed loan: {principal} {currency}")
        except Exception as e:
            return ("FAIL", f"Error accessing entity: {str(e)}")


# Test 1: Entity helper creation
print("Test 1: Entity helper creation")
rules = [MockLoanRule()]
entity_data = {
    "$schema": "file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json",
    "id": "LOAN-TEST-001",
    "financial": {
        "principal_amount": 100000,
        "currency": "USD"
    }
}
required_data = {}

executor = RuleExecutor(rules, entity_data, required_data)
assert executor.entity_helper is not None, "Entity helper should be created"
assert isinstance(executor.entity_helper, LoanV1), "Entity helper should be LoanV1 instance"
print("  ✓ Entity helper created")
print(f"  ✓ Entity helper type: {type(executor.entity_helper).__name__}")

# Test 2: Entity helper injection into rule
print("\nTest 2: Entity helper injection")
rule_configs = [{"rule_id": "mock_loan_rule_v1"}]
results = executor.execute_hierarchical(rule_configs)

result = results[0]
assert result["status"] == "PASS", f"Rule should pass, got: {result['status']} - {result['message']}"
assert "100000" in result["message"], "Should have accessed principal amount"
assert "USD" in result["message"], "Should have accessed currency"
print(f"  ✓ Entity helper injected successfully")
print(f"  ✓ Rule message: {result['message']}")

# Test 3: No entity helper when no rules
print("\nTest 3: No entity helper when rules list is empty")
executor_empty = RuleExecutor([], entity_data, required_data)
assert executor_empty.entity_helper is None, "Entity helper should be None for empty rules"
print("  ✓ No entity helper created for empty rules list")

# Test 4: Entity helper provides domain-aware access
print("\nTest 4: Domain-aware data access through helper")
loan_helper = executor.entity_helper
# Access logical domain names
principal = loan_helper.principal
currency = loan_helper.currency
assert principal == 100000, f"Principal should be 100000, got {principal}"
assert currency == "USD", f"Currency should be USD, got {currency}"
print(f"  ✓ Domain-aware access: principal={principal}, currency={currency}")

print("\n" + "="*50)
print("✓ All entity helper integration tests passed!")
print("="*50)
