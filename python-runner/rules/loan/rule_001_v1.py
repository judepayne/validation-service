"""
Rule 001 v1: JSON Schema Validation

Validates that loan entity data conforms to its declared JSON schema.
"""

import json
import urllib.request
from jsonschema import validate, ValidationError, Draft7Validator
from typing import Tuple

from rules.base import ValidationRule


class Rule(ValidationRule):
    """Validates loan entity data against its JSON schema."""

    def validates(self) -> str:
        """Return entity type this rule validates."""
        return "loan"

    def required_data(self) -> list[str]:
        """
        Return list of required data vocabulary terms.

        This rule only needs the entity data itself (no additional data).
        """
        return []

    def description(self) -> str:
        """Return plain English description of rule."""
        return "Entity data must conform to its declared JSON schema"

    def set_required_data(self, data: dict) -> None:
        """
        Receive required data before execution.

        Args:
            data: Dict with vocabulary terms as keys (empty for this rule)
        """
        pass  # No required data needed

    def run(self) -> Tuple[str, str]:
        """
        Execute schema validation rule.

        Note: self.entity is injected by rule executor and provides access to
        the raw entity_data via self.entity._data

        Returns:
            Tuple of (status, message)
            status: "PASS" | "FAIL" | "NORUN"
            message: Error description (empty string for PASS)
        """
        # Get raw entity data (includes $schema field)
        entity_data = self.entity._data

        # Check if $schema field is present
        schema_url = entity_data.get("$schema")
        if not schema_url:
            return ("FAIL", "Entity data missing required $schema field")

        # Fetch schema directly from URI (supports file:// and https://)
        try:
            with urllib.request.urlopen(schema_url, timeout=10) as response:
                schema = json.loads(response.read())
        except Exception as e:
            return ("NORUN", f"Failed to fetch schema from {schema_url}: {str(e)}")

        # Validate entity data against schema
        try:
            validate(instance=entity_data, schema=schema)
            return ("PASS", "")
        except ValidationError as e:
            # Extract meaningful error message
            error_path = " -> ".join(str(p) for p in e.path) if e.path else "root"
            return ("FAIL",
                    f"Schema validation failed at {error_path}: {e.message}")
        except Exception as e:
            return ("FAIL", f"Schema validation error: {str(e)}")
