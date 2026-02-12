"""
Case conversion utilities for babashka pod protocol compatibility.

Babashka/Clojure uses kebab-case for function names (get-required-data),
while Python uses snake_case (get_required_data). This module provides
bidirectional conversion for protocol compatibility.

Used by:
- pods_transport.py to convert incoming function names from Clojure
- Future: Response encoding if needed for protocol extensions

Example:
    >>> kebab_to_snake('get-required-data')
    'get_required_data'
    >>> snake_to_kebab('get_required_data')
    'get-required-data'
"""

def kebab_to_snake(name: str) -> str:
    """Convert kebab-case to snake_case: 'get-required-data' -> 'get_required_data'"""
    return name.replace("-", "_")

def snake_to_kebab(name: str) -> str:
    """Convert snake_case to kebab-case: 'get_required_data' -> 'get-required-data'"""
    return name.replace("_", "-")
