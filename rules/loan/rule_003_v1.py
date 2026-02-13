"""Validate loan status field"""

from rules.base import ValidationRule


class Rule(ValidationRule):
    """Validates that loan status is present and has a valid value."""

    def validates(self) -> str:
        return "loan"

    def required_data(self) -> list:
        return []

    def description(self) -> str:
        return "Loan status must be one of: active, paid_off, defaulted, written_off"

    def set_required_data(self, data: dict) -> None:
        pass

    def run(self) -> tuple:
        """Check that status field exists and has valid value."""
        valid_statuses = ["active", "paid_off", "defaulted", "written_off"]

        status = self.entity.status

        if status is None:
            return ("FAIL", "Loan status is missing")

        if status not in valid_statuses:
            return ("FAIL", f"Invalid loan status '{status}'. Must be one of: {', '.join(valid_statuses)}")

        return ("PASS", "")
