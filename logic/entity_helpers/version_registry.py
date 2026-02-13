"""
Version Registry - Schema Version Routing System

Maps schema URLs to versioned entity helper classes, enabling multiple schema versions
to coexist simultaneously. Critical for zero-downtime migrations when different systems
send v1 and v2 data concurrently.

## Problem Solved

When entity data models evolve (field renames, restructuring), validation rules must
continue working without breaking. The version registry routes each piece of entity data
to the correct helper class based on its declared `$schema` URL.

Example scenario:
- Old system sends loans with `loan_number` field (v1.0.0 schema)
- New system sends loans with `reference_number` field (v2.0.0 schema)
- Rules use stable logical properties: `loan.reference`
- Registry routes v1 data → LoanV1 (reads `loan_number`)
- Registry routes v2 data → LoanV2 (reads `reference_number`)
- Rules work unchanged for both versions

## How It Works

1. **Entity data declares schema version:**
   ```json
   {
     "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
     "loan_number": "LN-001",
     ...
   }
   ```

2. **Config maps schema URLs to helper classes:**
   ```yaml
   schema_to_helper_mapping:
     "https://bank.example.com/schemas/loan/v1.0.0": "loan_v1.LoanV1"
     "https://bank.example.com/schemas/loan/v2.0.0": "loan_v2.LoanV2"

   default_helpers:
     loan: "loan_v1.LoanV1"  # Used when $schema is absent
   ```

3. **Registry resolves at runtime:**
   ```python
   registry = get_registry(config_path)
   helper_class = registry.get_helper_class(entity_data, entity_type)
   helper = helper_class(entity_data, track_access=True)
   ```

4. **Helper provides stable interface:**
   ```python
   # Works for both v1 and v2!
   loan_ref = helper.reference  # LoanV1 reads loan_number, LoanV2 reads reference_number
   ```

## Version Resolution Order

1. **Exact match:** `$schema` URL matches entry in `schema_to_helper_mapping`
2. **Minor version fallback:** v1.2.0 falls back to v1.0.0 (if `allow_minor_version_fallback: true`)
3. **Default helper:** Entity type matches entry in `default_helpers` (when `$schema` absent)
4. **ValueError:** No match found (strict major version check if enabled)

## Configuration Format

```yaml
# Schema URL → helper class mapping
schema_to_helper_mapping:
  "https://bank.example.com/schemas/loan/v1.0.0": "loan_v1.LoanV1"
  "https://bank.example.com/schemas/loan/v2.0.0": "loan_v2.LoanV2"

# Fallback when $schema is missing
default_helpers:
  loan: "loan_v1.LoanV1"
  facility: "facility_v1.FacilityV1"

# Version compatibility rules
version_compatibility:
  allow_minor_version_fallback: true  # v1.1.0 → v1.0.0 helper
  strict_major_version: true          # Reject unknown major versions
```

## Usage

**Typical usage (via factory function):**
```python
from entity_helpers import create_entity_helper

# Factory automatically uses registry
helper = create_entity_helper("loan", entity_data, track_access=True)
```

**Direct usage:**
```python
from entity_helpers.version_registry import get_registry

registry = get_registry("local-config.yaml")
helper_class = registry.get_helper_class(entity_data, "loan")
helper = helper_class(entity_data)
```

**Testing:**
```python
from entity_helpers.version_registry import reset_registry

# Reset singleton between tests
reset_registry()
registry = VersionRegistry("test_local-config.yaml")
```

## Adding New Schema Versions

1. Create versioned helper class: `entity_helpers/loan_v3.py`
2. Add mapping to `business-config.yaml`:
   ```yaml
   "https://bank.example.com/schemas/loan/v3.0.0": "loan_v3.LoanV3"
   ```
3. Restart service (registry reads config at startup)

No code changes needed. Rules continue using stable logical properties.

## Key Design Principles

- **Config-driven:** Version mappings in business-config.yaml, not hardcoded
- **Singleton pattern:** One registry per process, lazily initialized
- **Minor version compatibility:** v1.1.0 data can use v1.0.0 helper
- **Explicit major versions:** New major versions require explicit helper classes
- **Fail-safe defaults:** Falls back to entity type when $schema is missing

## See Also

- `docs/HOW-VERSIONING-WORKS.md` - Detailed versioning guide
- `entity_helpers/__init__.py` - Factory function using this registry
- `entity_helpers/loan_v1.py`, `loan_v2.py` - Example versioned helpers
"""

import importlib
import json
import urllib.request
from typing import Optional, Type
import yaml


class VersionRegistry:
    """Maps schema URLs to entity helper classes via config."""

    def __init__(self, config_path: str):
        # Load config - handle two-tier configuration
        import os
        if 'local-config.yaml' in config_path or 'business_config_uri' in open(config_path).read():
            # Two-tier config - use ConfigLoader
            from core.config_loader import ConfigLoader
            config_loader = ConfigLoader(config_path)
            config = config_loader.get_business_config()
        else:
            # Single-tier config - load directly
            with open(config_path) as f:
                config = yaml.safe_load(f)

        self._schema_map = config.get("schema_to_helper_mapping", {})
        self._default_helpers = config.get("default_helpers", {})
        self._version_compat = config.get("version_compatibility", {})
        self._allow_minor_fallback = self._version_compat.get("allow_minor_version_fallback", False)
        self._strict_major = self._version_compat.get("strict_major_version", True)

    def detect_schema_version(self, entity_data: dict) -> Optional[str]:
        """
        Extract and normalize the $schema URL from entity data.

        If $schema is a fetchable URI (file:// or https:// ending in .json),
        fetch it and extract the canonical $id. Otherwise return as-is.
        """
        schema_uri = entity_data.get("$schema")
        if not schema_uri:
            return None

        # If it's a fetchable URI ending in .json, fetch and extract $id
        if schema_uri.endswith(".json") and ("file://" in schema_uri or "https://" in schema_uri):
            try:
                with urllib.request.urlopen(schema_uri, timeout=10) as response:
                    schema = json.loads(response.read())
                    # Return the canonical $id from the schema
                    return schema.get("$id", schema_uri)
            except Exception:
                # If fetch fails, fall back to using the URI as-is
                return schema_uri

        return schema_uri

    def parse_schema_url(self, schema_url: str) -> tuple:
        """
        Parse schema URL into (entity_type, version, major).

        Example: "https://bank.example.com/schemas/loan/v1.0.0"
        Returns: ("loan", "1.0.0", "1")
        """
        # Extract entity type and version from URL path
        # Expected format: .../schemas/{entity_type}/v{version}
        parts = schema_url.rstrip("/").split("/")
        if len(parts) < 2:
            raise ValueError(f"Cannot parse schema URL: {schema_url}")

        version_part = parts[-1]  # e.g., "v1.0.0"
        entity_part = parts[-2]   # e.g., "loan"

        if not version_part.startswith("v"):
            raise ValueError(f"Version segment must start with 'v': {version_part}")

        version = version_part[1:]  # "1.0.0"
        major = version.split(".")[0]  # "1"

        return (entity_part, version, major)

    def get_helper_class(self, entity_data: dict, entity_type: str = None) -> Type:
        """
        Resolve the correct helper class for the given entity data.

        Resolution order:
        1. $schema URL in entity_data → exact match in schema_to_helper_mapping
        2. $schema URL with minor version fallback (if configured)
        3. entity_type → default_helpers mapping
        4. ValueError if nothing matches
        """
        schema_url = self.detect_schema_version(entity_data)

        if schema_url:
            # Try exact match
            helper_path = self._schema_map.get(schema_url)
            if helper_path:
                return self._load_helper_class(helper_path)

            # Try minor version fallback
            if self._allow_minor_fallback:
                helper_path = self._try_minor_version_fallback(schema_url)
                if helper_path:
                    return self._load_helper_class(helper_path)

            # If strict_major_version, reject unknown major versions
            if self._strict_major:
                try:
                    entity_part, version, major = self.parse_schema_url(schema_url)
                    # Check if any registered URL has same entity and major version
                    for registered_url in self._schema_map:
                        try:
                            reg_entity, reg_version, reg_major = self.parse_schema_url(registered_url)
                            if reg_entity == entity_part and reg_major == major:
                                # Same entity + major, different minor - should have been caught by fallback
                                break
                        except ValueError:
                            continue
                    else:
                        raise ValueError(
                            f"No helper registered for schema URL: {schema_url}. "
                            f"Unknown major version."
                        )
                except ValueError as e:
                    if "No helper registered" in str(e):
                        raise
                    # URL parse error - fall through to default

        # Fall back to entity_type default
        resolved_type = entity_type
        if not resolved_type and schema_url:
            try:
                resolved_type, _, _ = self.parse_schema_url(schema_url)
            except ValueError:
                pass

        if resolved_type:
            helper_path = self._default_helpers.get(resolved_type)
            if helper_path:
                return self._load_helper_class(helper_path)

        raise ValueError(
            f"Cannot resolve helper class. "
            f"schema_url={schema_url!r}, entity_type={entity_type!r}"
        )

    def _try_minor_version_fallback(self, schema_url: str) -> Optional[str]:
        """
        For schema URL with minor version (e.g., v1.1.0),
        find registered helper for same major (e.g., v1.0.0).
        """
        try:
            entity_type, version, major = self.parse_schema_url(schema_url)
        except ValueError:
            return None

        for registered_url, helper_path in self._schema_map.items():
            try:
                reg_entity, reg_version, reg_major = self.parse_schema_url(registered_url)
                if reg_entity == entity_type and reg_major == major:
                    return helper_path
            except ValueError:
                continue

        return None

    def _load_helper_class(self, helper_path: str) -> Type:
        """
        Dynamically load a helper class from a dotted path.

        Args:
            helper_path: e.g., "loan_v1.LoanV1" or "loan_v2.LoanV2"
        """
        module_name, class_name = helper_path.rsplit(".", 1)
        # Import from entity_helpers package
        module = importlib.import_module(f"entity_helpers.{module_name}")
        return getattr(module, class_name)


_registry: Optional[VersionRegistry] = None


def get_registry(config_path: str = None) -> VersionRegistry:
    """Get or initialize the singleton VersionRegistry."""
    global _registry
    if _registry is None:
        if config_path is None:
            raise RuntimeError(
                "VersionRegistry not initialized. Call get_registry(config_path) first."
            )
        _registry = VersionRegistry(config_path)
    return _registry


def reset_registry():
    """Reset the singleton registry (for testing)."""
    global _registry
    _registry = None
