"""
Rule 002 v1: Loan Financial Soundness

Validates that loan has valid financial parameters:
- Principal amount is positive
- Maturity date is after origination date
- Interest rate is non-negative
"""

from typing import Tuple

from rules.base import ValidationRule


class Rule(ValidationRule):
    """Validates loan financial parameters are sound."""

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
        return "Loan must have positive principal, valid dates, and non-negative interest rate"

    def set_required_data(self, data: dict) -> None:
        """
        Receive required data before execution.

        Args:
            data: Dict with vocabulary terms as keys (empty for this rule)
        """
        pass  # No required data needed

    def run(self) -> Tuple[str, str]:
        """
        Execute financial soundness validation.

        Note: self.entity is a Loan helper instance (provided by rule executor)

        Returns:
            Tuple of (status, message)
            status: "PASS" | "FAIL" | "NORUN"
            message: Error description (empty string for PASS)
        """
        errors = []

        # Check 1: Principal amount must be positive
        try:
            principal = self.entity.principal
            if principal <= 0:
                errors.append(f"Principal amount must be positive, got {principal}")
        except AttributeError as e:
            return ("NORUN", f"Cannot access principal amount: {str(e)}")

        # Check 2: Interest rate must be non-negative
        try:
            interest_rate = self.entity.rate  # Use logical property name
            if interest_rate < 0:
                errors.append(f"Interest rate cannot be negative, got {interest_rate}")
        except AttributeError:
            # Interest rate might be optional in some schemas
            pass

        # Check 3: Maturity date must be after inception (origination) date
        try:
            inception = self.entity.inception  # Logical name: inception
            maturity = self.entity.maturity    # Logical name: maturity

            if not inception or not maturity:
                errors.append("Missing required date fields (inception or maturity)")
            else:
                # Dates are already parsed as date objects by the Loan helper
                if maturity <= inception:
                    errors.append(
                        f"Maturity date ({maturity}) must be after inception date ({inception})"
                    )
        except AttributeError as e:
            return ("NORUN", f"Cannot access date fields: {str(e)}")

        # Check 4: Outstanding balance should not exceed principal
        try:
            principal = self.entity.principal
            balance = self.entity.balance  # Use logical property name
            if balance and balance > principal:
                errors.append(
                    f"Outstanding balance ({balance}) exceeds original principal ({principal})"
                )
        except AttributeError:
            # Outstanding balance might be optional
            pass

        # Return result
        if errors:
            return ("FAIL", "; ".join(errors))
        else:
            return ("PASS", "")
