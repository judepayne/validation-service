"""Validate loan balance constraints"""

from rules.base import ValidationRule


class Rule(ValidationRule):
    """Validates outstanding balance constraints based on loan status."""

    def validates(self) -> str:
        return "loan"

    def required_data(self) -> list:
        return []

    def description(self) -> str:
        return "Outstanding balance must not exceed principal; paid_off loans must have zero balance"

    def set_required_data(self, data: dict) -> None:
        pass

    def run(self) -> tuple:
        """Check balance constraints based on status."""
        status = self.entity.status
        principal = self.entity.principal
        balance = self.entity.balance

        # Check balance doesn't exceed principal
        if balance > principal:
            return ("FAIL", f"Outstanding balance ({balance}) exceeds principal amount ({principal})")

        # Status-specific validation
        if status == "paid_off":
            if balance != 0:
                return ("FAIL", f"Paid-off loan must have zero balance, got {balance}")

        if status == "active":
            if balance == 0:
                return ("FAIL", "Active loan cannot have zero outstanding balance")

        return ("PASS", "")
