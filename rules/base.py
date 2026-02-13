"""
Abstract base class for validation rules.

All rules must inherit from ValidationRule and implement the six required methods.
The rule executor injects self.entity before calling run().
"""

from abc import ABC, abstractmethod
from typing import Tuple


class ValidationRule(ABC):
    """
    Abstract base class for all validation rules.

    The rule executor injects the entity helper instance as self.entity
    before calling run(). Rules access entity data through this helper
    using logical property names (e.g. self.entity.principal) rather
    than physical paths into the raw data dict.

    The rule ID is injected at instantiation time by the rule loader,
    derived from the filename. This eliminates the need for hardcoded
    IDs in rule implementations.
    """

    def __init__(self, rule_id: str):
        """
        Initialize the rule with its identifier.

        Args:
            rule_id: Unique rule identifier (derived from filename by loader)
        """
        self._rule_id = rule_id

    def get_id(self) -> str:
        """Return unique rule identifier (e.g. 'rule_001_v1')."""
        return self._rule_id

    @abstractmethod
    def validates(self) -> str:
        """Return entity type this rule validates (e.g. 'loan')."""

    @abstractmethod
    def required_data(self) -> list[str]:
        """
        Return list of required data vocabulary terms.

        Terms are passed to set_required_data() before run() is called.
        Examples: [], ["parent"], ["all_siblings"]
        """

    @abstractmethod
    def description(self) -> str:
        """Return plain English description of what this rule checks."""

    @abstractmethod
    def set_required_data(self, data: dict) -> None:
        """
        Receive required data before execution.

        Args:
            data: Dict keyed by vocabulary terms from required_data()
        """

    @abstractmethod
    def run(self) -> Tuple[str, str]:
        """
        Execute the validation rule.

        Returns:
            Tuple of (status, message) where:
            - status: "PASS" | "FAIL" | "NORUN"
            - message: Error description (empty string for PASS)
        """
