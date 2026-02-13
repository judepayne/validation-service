"""
Case conversion utilities for babashka pod protocol compatibility.

Babashka/Clojure uses kebab-case for function names (get-required-data),
while Python uses snake_case (get_required_data). This module provides
conversion for protocol compatibility.

Used by:
- pods_transport.py to convert incoming function names from Clojure

Example:
    >>> kebab_to_snake('get-required-data')
    'get_required_data'
"""

def kebab_to_snake(name: str) -> str:
    """Convert kebab-case to snake_case: 'get-required-data' -> 'get_required_data'"""
    return name.replace("-", "_")
