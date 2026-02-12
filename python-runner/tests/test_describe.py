#!/usr/bin/env python3
"""Test what describe response looks like"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bencodepy as bencode

# Create describe response
response = {
    "id": "1",
    "value": {
        "format": "json",
        "namespaces": [{
            "name": "pod.validation-runner",
            "vars": [
                {"name": "get-required-data"},
                {"name": "validate"},
                {"name": "discover-rules"}
            ]
        }],
        "ops": {
            "shutdown": {}
        }
    }
}

print("Python dict:")
print(response)

print("\nEncoded:")
encoded = bencode.encode(response)
print(encoded)

print("\nDecoded:")
decoded = bencode.decode(encoded)
print(decoded)
