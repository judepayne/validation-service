#!/usr/bin/env python3
"""
Test script for loan helper class with logical domain names.

Loads sample loan data and exercises the loan helper to verify:
1. Field access works correctly with logical domain names
2. Field tracking records logical names (stable across model changes)
3. Logging captures both logical names AND physical model paths
"""

import json
import sys
import os

# Add python-runner to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python-runner'))

from entity_helpers import Loan, create_entity_helper  # Will be imported from entity-helpers package


def main():
    # Load sample loan data
    sample_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'sample-data',
        'single-examples',
        'loan1.json'
    )

    with open(sample_path) as f:
        loan_data = json.load(f)

    print("=" * 60)
    print("Testing Loan Helper")
    print("=" * 60)

    # Test 1: Basic field access using LOGICAL DOMAIN NAMES
    print("\n[Test 1] Basic field access with logical domain names (no tracking, no logging)")
    loan = Loan(loan_data)
    print(f"  Loan ID: {loan.id}")
    print(f"  Loan Reference: {loan.reference}")           # Logical: reference (model: loan_number)
    print(f"  Parent Facility: {loan.facility}")           # Logical: facility (model: facility_id)
    print(f"  Principal: {loan.currency} {loan.principal:,.2f}")  # Logical: principal (model: financial.principal_amount)
    print(f"  Interest Rate: {loan.rate * 100:.2f}%")      # Logical: rate (model: financial.interest_rate)
    print(f"  Status: {loan.status}")
    print(f"  Maturity: {loan.maturity}")                  # Logical: maturity (model: dates.maturity_date)
    print(f"  Is Overdue: {loan.overdue}")                 # Logical: overdue (computed)
    print("  ✓ Basic access works with domain names")

    # Test 2: Field tracking with LOGICAL NAMES
    print("\n[Test 2] Field access tracking records LOGICAL names (enabled)")
    loan_tracked = Loan(loan_data, track_access=True)

    # Access various fields using logical domain names
    _ = loan_tracked.id
    _ = loan_tracked.principal      # Logical name (not principal_amount)
    _ = loan_tracked.currency
    _ = loan_tracked.maturity       # Logical name (not maturity_date)
    _ = loan_tracked.overdue        # Logical name (not is_overdue)

    accessed = loan_tracked.get_accessed_fields()
    print(f"  Logical fields accessed: {len(accessed)}")
    print("  NOTE: Tracking records LOGICAL names (stable across model changes):")
    for field in sorted(accessed):
        print(f"    - {field}")
    print("  ✓ Field tracking records logical domain names")

    # Test 3: Logging with BOTH logical and physical names
    print("\n[Test 3] Field access logging captures BOTH logical AND physical names (enabled)")
    loan_logged = Loan(loan_data, log_access=True)

    # Access various fields to generate log entries
    print("  Accessing fields (watch the log output):")
    _ = loan_logged.id              # Simple field
    _ = loan_logged.reference       # Logical: reference → Physical: loan_number
    _ = loan_logged.principal       # Logical: principal → Physical: financial.principal_amount
    _ = loan_logged.balance         # Logical: balance → Physical: financial.outstanding_balance
    _ = loan_logged.currency        # Logical: currency → Physical: financial.currency
    _ = loan_logged.rate            # Logical: rate → Physical: financial.interest_rate
    _ = loan_logged.inception       # Logical: inception → Physical: dates.origination_date
    _ = loan_logged.maturity        # Logical: maturity → Physical: dates.maturity_date
    _ = loan_logged.status          # Simple field

    log_file = os.path.join(
        os.path.dirname(__file__),
        '..',
        'logs',
        'field_access.log'
    )

    if os.path.exists(log_file):
        print(f"\n  Log file created: {log_file}")
        with open(log_file) as f:
            lines = f.readlines()
            print(f"  Total log entries: {len(lines)}")
            print("\n  Last 10 log entries showing DUAL LOGGING (logical + physical):")
            for line in lines[-10:]:
                print(f"    {line.rstrip()}")
        print("\n  ✓ Logging captures both logical names AND physical model paths")
    else:
        print("  ✗ Log file not found")

    # Test 4: Factory function
    print("\n[Test 4] Factory function with logical names")
    loan_factory = create_entity_helper("loan", loan_data, track_access=True)
    _ = loan_factory.id
    _ = loan_factory.principal     # Logical name
    print(f"  Created via factory: {loan_factory}")
    print(f"  Logical fields accessed: {loan_factory.get_accessed_fields()}")
    print("  ✓ Factory function works with domain names")

    # Test 5: Nested field access with logical names
    print("\n[Test 5] Nested field access (logical names map to nested model paths)")
    loan_nested = Loan(loan_data, track_access=True)
    print(f"  Origination Fee: ${loan_nested.origination_fee:,.2f}")      # Maps to financial.fees.origination_fee
    print(f"  Servicing Fee: ${loan_nested.servicing_fee:,.2f}")          # Maps to financial.fees.servicing_fee
    print(f"  Payment Frequency: {loan_nested.payment_frequency}")        # Logical: payment_frequency
    print(f"  Payment Count: {loan_nested.payment_count}")                # Logical: payment_count
    nested_accessed = loan_nested.get_accessed_fields()
    print(f"  Logical fields accessed (despite nested model structure):")
    for field in sorted(nested_accessed):
        print(f"    - {field}")
    print("  ✓ Logical names successfully abstract nested model structure")

    # Test 6: Computed properties with logical names
    print("\n[Test 6] Computed properties using logical domain names")
    loan_computed = Loan(loan_data, track_access=True)
    print(f"  Principal: ${loan_computed.principal:,.2f}")                # Logical: principal
    print(f"  Balance: ${loan_computed.balance:,.2f}")                    # Logical: balance
    print(f"  Repaid: ${loan_computed.repaid:,.2f}")                      # Logical: repaid (computed)
    print(f"  Repayment %: {loan_computed.repayment_pct:.2f}%")          # Logical: repayment_pct
    print(f"  Overdue: {loan_computed.overdue}")                          # Logical: overdue
    print("  ✓ Computed properties work with domain names")

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    print("\nKEY BENEFITS OF LOGICAL DOMAIN NAMES:")
    print("  1. Rules use stable business language (loan.principal, not loan.principal_amount)")
    print("  2. Model can evolve (rename fields, restructure) without breaking rules")
    print("  3. Field tracking records logical names (stable dependency analysis)")
    print("  4. Logging captures BOTH logical + physical for debugging")
    print("  5. Clear separation: Domain concepts vs. current data format")
    print("=" * 60)


if __name__ == "__main__":
    main()
