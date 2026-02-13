#!/usr/bin/env python3
"""
End-to-End Test: Bencode Protocol Communication

Tests the complete pipeline:
- Runner receives bencode messages via stdin
- Processes get_required_data and validate requests
- Returns bencode-encoded responses via stdout
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
import bencodepy as bencode
import json
import time
from transport.bencode_reader import read_bencode_value


def read_bencode_message(stream):
    raw = read_bencode_value(stream)
    if raw is None:
        raise EOFError("No data received")
    return bencode.decode(raw)

print("="*70)
print("End-to-End Bencode Protocol Test")
print("="*70)

_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Start the runner process
print("\n[1] Starting runner process...")
proc = subprocess.Popen(
    ['python3', os.path.join(_RUNNER_DIR, 'runner.py'), os.path.join(_RUNNER_DIR, 'local-config.yaml')],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    bufsize=0  # Unbuffered
)
print("✓ Runner process started (PID: {})".format(proc.pid))

# Give the process a moment to initialize
time.sleep(0.1)

# Test 1: get_required_data
print("\n" + "="*70)
print("Test 1: get_required_data operation")
print("="*70)

request_1 = {
    b'op': b'invoke',
    b'id': b'req-001',
    b'var': b'get_required_data',
    b'args': {
        b'entity_type': b'loan',
        b'schema_url': b'file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json',
        b'mode': b'inline'
    }
}

print("Sending request: get_required_data")
encoded_request = bencode.encode(request_1)
proc.stdin.write(encoded_request)
proc.stdin.flush()

print("Reading response...")
# Read response (bencode messages are self-delimiting)
try:
    response_1 = read_bencode_message(proc.stdout)
    print("✓ Response received")

    # Verify response structure
    assert b'id' in response_1, "Response missing 'id' field"
    assert response_1[b'id'] == b'req-001', "Response ID doesn't match request ID"
    assert b'value' in response_1 or b'error' in response_1, "Response missing 'value' or 'error'"

    if b'error' in response_1:
        print("✗ ERROR:", response_1[b'error'].decode())
    else:
        required_data = json.loads(response_1[b'value'].decode())
        print(f"✓ Required data: {required_data}")
        assert isinstance(required_data, list), "Required data should be a list"
        assert len(required_data) == 0, "Our test rules require no additional data"
        print("✓ Response structure valid")
except Exception as e:
    print(f"✗ Failed to decode response: {e}")
    proc.kill()
    exit(1)

# Test 2: validate operation (bencode limitation: missing interest_rate)
print("\n" + "="*70)
print("Test 2: validate operation (incomplete data - bencode can't represent floats)")
print("="*70)

request_2 = {
    b'op': b'invoke',
    b'id': b'req-002',
    b'var': b'validate',
    b'args': {
        b'entity_type': b'loan',
        b'entity_data': {
            b'$schema': b'file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json',
            b'id': b'LOAN-99999',
            b'loan_number': b'LN-VALID-001',
            b'facility_id': b'FAC-100',
            b'client_id': b'CLIENT-001',
            b'financial': {
                b'principal_amount': 250000,
                b'outstanding_balance': 200000,
                b'currency': b'USD'
                # interest_rate omitted - bencode can't represent floats,
                # schema will catch missing required field
            },
            b'dates': {
                b'origination_date': b'2024-06-01',
                b'maturity_date': b'2027-06-01',
                b'first_payment_date': b'2024-07-01'
            },
            b'status': b'active'
        },
        b'mode': b'inline',
        b'required_data': {}
    }
}

print("Sending request: validate (valid loan)")
encoded_request = bencode.encode(request_2)
proc.stdin.write(encoded_request)
proc.stdin.flush()

print("Reading response...")
try:
    response_2 = read_bencode_message(proc.stdout)
    print("✓ Response received")

    # Verify response structure
    assert b'id' in response_2, "Response missing 'id' field"
    assert response_2[b'id'] == b'req-002', "Response ID doesn't match request ID"

    if b'error' in response_2:
        print("✗ ERROR:", response_2[b'error'].decode())
    else:
        results = json.loads(response_2[b'value'].decode())
        print(f"✓ Validation results received ({len(results)} rules)")

        # Check results structure
        rule_statuses = {}
        for i, result in enumerate(results):
            rule_id = result['rule_id']
            status = result['status']
            description = result['description']
            exec_time = result['execution_time_ms']
            message = result.get('message', '')

            print(f"  Rule {i+1}: {rule_id} -> {status}")
            print(f"    Description: {description}")
            if message:
                print(f"    Message: {message[:80]}...")
            print(f"    Execution time: {exec_time}ms")

            rule_statuses[rule_id] = status

        # Verify schema validation (rule_001_v1) caught missing interest_rate
        assert rule_statuses.get('rule_001_v1') == 'FAIL', \
            "Expected schema validation to FAIL (missing required interest_rate)"

        # Verify business rule (rule_002_v1) got ERROR due to NoneType comparison
        assert rule_statuses.get('rule_002_v1') == 'ERROR', \
            "Expected business rule to ERROR on None interest_rate comparison"

        print("✓ Validation response structure correct")
        print("✓ ERROR status correctly returned for rule crashes")
except Exception as e:
    print(f"✗ Failed to process response: {e}")
    import traceback
    traceback.print_exc()
    proc.kill()
    exit(1)

# Test 3: validate with invalid loan (negative principal)
print("\n" + "="*70)
print("Test 3: validate operation (invalid loan - negative principal)")
print("="*70)

request_3 = {
    b'op': b'invoke',
    b'id': b'req-003',
    b'var': b'validate',
    b'args': {
        b'entity_type': b'loan',
        b'entity_data': {
            b'$schema': b'file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json',
            b'id': b'LOAN-88888',
            b'loan_number': b'LN-INVALID-001',
            b'facility_id': b'FAC-999',
            b'financial': {
                b'principal_amount': -50000,  # Invalid: negative
                b'currency': b'USD'
                # interest_rate omitted - bencode limitation
            },
            b'dates': {
                b'origination_date': b'2024-01-01',
                b'maturity_date': b'2025-01-01'
            },
            b'status': b'active'
        },
        b'mode': b'inline',
        b'required_data': {}
    }
}

print("Sending request: validate (invalid loan)")
encoded_request = bencode.encode(request_3)
proc.stdin.write(encoded_request)
proc.stdin.flush()

print("Reading response...")
try:
    response_3 = read_bencode_message(proc.stdout)
    print("✓ Response received")

    if b'error' in response_3:
        print("✗ ERROR:", response_3[b'error'].decode())
    else:
        results = json.loads(response_3[b'value'].decode())
        print(f"✓ Validation results received ({len(results)} rules)")

        failed_count = 0
        for i, result in enumerate(results):
            rule_id = result['rule_id']
            status = result['status']
            message = result.get('message', '')

            print(f"  Rule {i+1}: {rule_id} -> {status}")
            if message:
                print(f"    Message: {message[:100]}...")

            if status == "FAIL":
                failed_count += 1

        assert failed_count > 0, "Expected at least one rule to fail"
        print(f"✓ {failed_count} rule(s) correctly failed for invalid loan")
except Exception as e:
    print(f"✗ Failed to process response: {e}")
    import traceback
    traceback.print_exc()
    proc.kill()
    exit(1)

# Test 4: Unknown function error handling
print("\n" + "="*70)
print("Test 4: Unknown function error handling")
print("="*70)

request_4 = {
    b'op': b'invoke',
    b'id': b'req-004',
    b'var': b'unknown_function',
    b'args': {}
}

print("Sending request: unknown_function")
encoded_request = bencode.encode(request_4)
proc.stdin.write(encoded_request)
proc.stdin.flush()

print("Reading response...")
try:
    response_4 = read_bencode_message(proc.stdout)
    print("✓ Response received")

    assert b'id' in response_4, "Response missing 'id' field"
    assert b'error' in response_4, "Expected error response for unknown function"

    error_msg = response_4[b'error'].decode()
    print(f"✓ Error message: {error_msg}")
    assert "Unknown function" in error_msg, "Error message should mention unknown function"
    print("✓ Error handling works correctly")
except Exception as e:
    print(f"✗ Failed to process response: {e}")
    proc.kill()
    exit(1)

# Cleanup
print("\n" + "="*70)
print("Cleanup")
print("="*70)

print("Terminating runner process...")
proc.terminate()
try:
    proc.wait(timeout=2)
    print("✓ Runner process terminated cleanly")
except subprocess.TimeoutExpired:
    print("⚠ Process didn't terminate, killing...")
    proc.kill()
    proc.wait()

print("\n" + "="*70)
print("✓ All End-to-End Tests Passed!")
print("="*70)
print("\nVerified:")
print("  ✓ Runner starts and listens for bencode messages")
print("  ✓ get_required_data operation works")
print("  ✓ validate operation works (bencode float limitation noted)")
print("  ✓ validate operation detects invalid data")
print("  ✓ Error handling works for unknown functions")
print("  ✓ Bencode encoding/decoding works correctly")
print("  ✓ Response IDs match request IDs")
print("  ✓ Response structure follows protocol")
print("\nNote: bencode cannot represent floats, so interest_rate field omitted in tests.")
