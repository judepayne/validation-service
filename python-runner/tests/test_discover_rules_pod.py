#!/usr/bin/env python3
"""Manual test for discover-rules pod function"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.validation_engine import ValidationEngine
import json

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


def main():
    print("\n=== Manual Test: discover-rules Pod Function ===\n")

    engine = ValidationEngine(CONFIG_PATH)

    # Call discover_rules (simulating what the pod would do)
    result = engine.discover_rules("loan", LOAN_V1_DATA, "quick")

    print("Result from discover_rules:")
    print(json.dumps(result, indent=2))

    print("\n=== Metadata Summary ===\n")
    for rule_id, metadata in result.items():
        print(f"Rule: {rule_id}")
        print(f"  Entity Type: {metadata['entity_type']}")
        print(f"  Description: {metadata['description']}")
        print(f"  Required Data: {metadata['required_data']}")
        print(f"  Field Dependencies: {len(metadata['field_dependencies'])} fields")
        for logical, physical in metadata['field_dependencies']:
            print(f"    - {logical} → {physical}")
        print(f"  Applicable Schemas: {len(metadata['applicable_schemas'])} versions")
        for schema in metadata['applicable_schemas']:
            print(f"    - {schema}")
        print()

    print("✓ Manual test completed successfully\n")


if __name__ == "__main__":
    main()
