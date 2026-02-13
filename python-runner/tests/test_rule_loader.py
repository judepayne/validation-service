#!/usr/bin/env python3
"""Test rule_loader with new single-class-name design"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add logic/ directory to sys.path for entity_helpers and rules imports
logic_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logic")
sys.path.insert(0, logic_dir)

from core.rule_loader import RuleLoader

# Configuration for testing
# Rules live in logic/rules/
config = {
    "master_rules_directory": os.path.join(logic_dir, "rules")
}

# Test rule loading with ID injection
loader = RuleLoader(config)

tests = [
    ('rule_001_v1', 'loan', 'Entity data must conform to its declared JSON schema'),
    ('rule_002_v1', 'loan', 'Loan must have positive principal, valid dates, and non-negative interest rate'),
]

print("Testing rule loading with ID injection:")
all_pass = True

for rule_id, expected_entity_type, expected_desc_fragment in tests:
    try:
        rule = loader._load_single_rule(rule_id)

        # Test 1: Rule ID is correctly injected
        actual_id = rule.get_id()
        id_match = actual_id == rule_id

        # Test 2: Entity type is correct
        entity_type_match = rule.validates() == expected_entity_type

        # Test 3: Description contains expected fragment
        desc_match = expected_desc_fragment in rule.description()

        all_match = id_match and entity_type_match and desc_match
        all_pass = all_pass and all_match

        status = "✓" if all_match else "✗"
        print(f"  {rule_id}: {status}")

        if not id_match:
            print(f"    ✗ ID mismatch: expected '{rule_id}', got '{actual_id}'")
        if not entity_type_match:
            print(f"    ✗ Entity type mismatch: expected '{expected_entity_type}', got '{rule.validates()}'")
        if not desc_match:
            print(f"    ✗ Description doesn't contain expected fragment")

    except Exception as e:
        print(f"  {rule_id}: ✗ (failed to load: {e})")
        all_pass = False

if all_pass:
    print("\n✓ All rules loaded correctly with injected IDs")
else:
    print("\n✗ Some rule loading tests failed")
    exit(1)
