#!/usr/bin/env python3
"""Simple bencode test"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
import bencodepy as bencode

# Create a simple request
request = {
    b'op': b'invoke',
    b'id': b'test-1',
    b'var': b'get_required_data',
    b'args': {
        b'entity_type': b'loan',
        b'entity_data': {b'id': b'LOAN-1'},
        b'mode': b'inline'
    }
}

print("Encoding request...")
encoded = bencode.encode(request)
print(f"Encoded length: {len(encoded)} bytes")
print(f"Encoded (first 100 bytes): {encoded[:100]}")

_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("\nStarting runner...")
proc = subprocess.Popen(
    ['python3', os.path.join(_RUNNER_DIR, 'runner.py')],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

print(f"Runner PID: {proc.pid}")

print("\nWriting request...")
try:
    proc.stdin.write(encoded)
    proc.stdin.flush()
    print("✓ Request written")
except Exception as e:
    print(f"✗ Error writing: {e}")
    proc.kill()
    sys.exit(1)

print("\nReading response byte-by-byte...")
try:
    response_bytes = bytearray()
    depth = 0
    started = False

    while True:
        byte = proc.stdout.read(1)
        if not byte:
            print(f"✗ EOF after {len(response_bytes)} bytes")
            print(f"Collected: {bytes(response_bytes)}")
            stderr = proc.stderr.read()
            if stderr:
                print(f"STDERR: {stderr.decode()}")
            break

        response_bytes.extend(byte)

        if not started and byte in (b'd', b'l'):
            started = True
            depth = 1
            print(f"Started message, type: {byte}")
        elif started:
            if byte in (b'd', b'l'):
                depth += 1
            elif byte == b'e':
                depth -= 1
                if depth == 0:
                    print(f"✓ Complete message ({len(response_bytes)} bytes)")
                    break

    if response_bytes:
        print(f"\nDecoding response...")
        response = bencode.decode(bytes(response_bytes))
        print(f"✓ Response: {response}")
except Exception as e:
    print(f"✗ Error reading: {e}")
    import traceback
    traceback.print_exc()

proc.terminate()
proc.wait()
