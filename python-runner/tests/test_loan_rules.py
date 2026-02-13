#!/usr/bin/env python3
"""Test loan validation rules"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add logic/ directory to sys.path for entity_helpers and rules imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logic"))

import json
from core.validation_engine import ValidationEngine

print("="*70)
print("Testing Loan Validation Rules")
print("="*70)

# Initialize validation engine
engine = ValidationEngine(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local-config.yaml"))

# Test Case 1: Valid loan - should PASS both rules
print("\n" + "="*70)
print("Test Case 1: Valid Loan (should PASS all rules)")
print("="*70)

valid_loan = {
    "$schema": "file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json",
    "id": "LOAN-12345",
    "loan_number": "LN-2024-00123",
    "facility_id": "FAC-789",
    "client_id": "CLIENT-001",
    "financial": {
        "principal_amount": 500000,
        "outstanding_balance": 450000,
        "currency": "USD",
        "interest_rate": 0.05,
        "interest_type": "fixed"
    },
    "dates": {
        "origination_date": "2024-01-15",
        "maturity_date": "2029-01-15",
        "first_payment_date": "2024-02-15"
    },
    "status": "active"
}

results = engine.validate("loan", valid_loan, "quick", {})

for result in results:
    print(f"\n{result['rule_id']}: {result['status']}")
    print(f"  Description: {result['description']}")
    if result['message']:
        print(f"  Message: {result['message']}")
    print(f"  Execution time: {result['execution_time_ms']}ms")

# Test Case 2: Invalid schema - missing required field
print("\n" + "="*70)
print("Test Case 2: Missing Required Field (should FAIL rule_001_v1)")
print("="*70)

invalid_loan_schema = {
    "$schema": "file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json",
    "id": "LOAN-99999",
    # Missing loan_number, facility_id (required fields)
    "financial": {
        "principal_amount": 100000,
        "currency": "USD",
        "interest_rate": 0.05
    },
    "dates": {
        "origination_date": "2024-01-01",
        "maturity_date": "2025-01-01"
    },
    "status": "active"
}

results = engine.validate("loan", invalid_loan_schema, "quick", {})

for result in results:
    print(f"\n{result['rule_id']}: {result['status']}")
    if result['message']:
        print(f"  Message: {result['message'][:150]}...")

# Test Case 3: Invalid business logic - negative principal
print("\n" + "="*70)
print("Test Case 3: Negative Principal (should FAIL rule_002_v1)")
print("="*70)

invalid_loan_business = {
    "$schema": "file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json",
    "id": "LOAN-88888",
    "loan_number": "LN-2024-BAD",
    "facility_id": "FAC-999",
    "financial": {
        "principal_amount": -50000,  # Invalid: negative
        "currency": "USD",
        "interest_rate": 0.05
    },
    "dates": {
        "origination_date": "2024-01-15",
        "maturity_date": "2029-01-15"
    },
    "status": "active"
}

results = engine.validate("loan", invalid_loan_business, "quick", {})

for result in results:
    print(f"\n{result['rule_id']}: {result['status']}")
    if result['message']:
        print(f"  Message: {result['message']}")

# Test Case 4: Invalid dates - maturity before origination
print("\n" + "="*70)
print("Test Case 4: Maturity Before Origination (should FAIL rule_002_v1)")
print("="*70)

invalid_dates_loan = {
    "$schema": "file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json",
    "id": "LOAN-77777",
    "loan_number": "LN-2024-DATE",
    "facility_id": "FAC-888",
    "financial": {
        "principal_amount": 100000,
        "currency": "USD",
        "interest_rate": 0.03
    },
    "dates": {
        "origination_date": "2029-01-15",  # After maturity!
        "maturity_date": "2024-01-15"      # Before origination!
    },
    "status": "active"
}

results = engine.validate("loan", invalid_dates_loan, "quick", {})

for result in results:
    print(f"\n{result['rule_id']}: {result['status']}")
    if result['message']:
        print(f"  Message: {result['message']}")

# Test Case 5: Rule crash — missing interest_rate causes TypeError in rule_002_v1
print("\n" + "="*70)
print("Test Case 5: Missing interest_rate (should ERROR in rule_002_v1)")
print("="*70)

missing_rate_loan = {
    "$schema": "file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json",
    "id": "LOAN-66666",
    "loan_number": "LN-2024-NORAT",
    "facility_id": "FAC-777",
    "financial": {
        "principal_amount": 200000,
        "currency": "USD"
        # interest_rate intentionally omitted
    },
    "dates": {
        "origination_date": "2024-01-15",
        "maturity_date": "2029-01-15"
    },
    "status": "active"
}

results = engine.validate("loan", missing_rate_loan, "quick", {})

for result in results:
    print(f"\n{result['rule_id']}: {result['status']}")
    if result['message']:
        print(f"  Message: {result['message']}")

# Test Case 6: Test get_required_data
print("\n" + "="*70)
print("Test Case 6: Get Required Data")
print("="*70)

required = engine.get_required_data("loan", valid_loan["$schema"], "quick")
print(f"Required data for loan inline validation: {required}")
print(f"✓ Both rules require no additional data (empty list expected)")

print("\n" + "="*70)
print("All Tests Complete!")
print("="*70)
