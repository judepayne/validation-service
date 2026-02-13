"""
Loan entity helper class v1 - Domain-Driven Data Access Layer.

Standalone versioned helper for loan schema v1.0.0.
Maps domain concepts to v1 physical field names.

LOGICAL → PHYSICAL MAPPING (v1.0.0 model):
- id → id
- reference → loan_number
- facility → facility_id
- client → client_id
- collateral → collateral_id
- principal → financial.principal_amount
- balance → financial.outstanding_balance
- currency → financial.currency
- rate → financial.interest_rate
- rate_type → financial.interest_type
- inception → dates.origination_date
- maturity → dates.maturity_date
- first_payment → dates.first_payment_date
- status → status
- purpose → loan_type
- secured → collateral_required
- payment_frequency → repayment_schedule.frequency
- payment_count → repayment_schedule.number_of_payments
"""

from typing import Optional, List, Tuple
from datetime import date, datetime


class LoanV1:
    """Helper class providing stable, domain-driven interface to loan v1.0.0 data."""

    def __init__(self, data: dict, track_access: bool = False):
        self._data = data
        self._track_access = track_access
        self._accesses: dict = {}  # (logical, physical) → None, ordered + deduplicated

    def _record_access(self, logical_name: str, model_path: str = None):
        """Record field access for dependency tracking."""
        if self._track_access:
            self._accesses[(logical_name, model_path)] = None

    def get_accesses(self) -> List[Tuple[str, str]]:
        """Return list of (logical_name, physical_path) pairs, ordered by first access."""
        return list(self._accesses.keys())

    @property
    def id(self) -> str:
        self._record_access("id", "id")
        return self._data.get("id", "")

    @property
    def reference(self) -> str:
        self._record_access("reference", "loan_number")
        return self._data.get("loan_number", "")

    @property
    def facility(self) -> str:
        self._record_access("facility", "facility_id")
        return self._data.get("facility_id", "")

    @property
    def client(self) -> str:
        self._record_access("client", "client_id")
        return self._data.get("client_id", "")

    @property
    def collateral(self) -> Optional[str]:
        self._record_access("collateral", "collateral_id")
        return self._data.get("collateral_id")

    @property
    def principal(self) -> float:
        self._record_access("principal", "financial.principal_amount")
        return self._data.get("financial", {}).get("principal_amount", 0.0)

    @property
    def balance(self) -> float:
        self._record_access("balance", "financial.outstanding_balance")
        return self._data.get("financial", {}).get("outstanding_balance", 0.0)

    @property
    def currency(self) -> str:
        self._record_access("currency", "financial.currency")
        return self._data.get("financial", {}).get("currency", "")

    @property
    def rate(self) -> Optional[float]:
        self._record_access("rate", "financial.interest_rate")
        return self._data.get("financial", {}).get("interest_rate")

    @property
    def rate_type(self) -> Optional[str]:
        self._record_access("rate_type", "financial.interest_type")
        return self._data.get("financial", {}).get("interest_type")

    @property
    def origination_fee(self) -> Optional[float]:
        self._record_access("origination_fee", "financial.fees.origination_fee")
        return self._data.get("financial", {}).get("fees", {}).get("origination_fee")

    @property
    def servicing_fee(self) -> Optional[float]:
        self._record_access("servicing_fee", "financial.fees.servicing_fee")
        return self._data.get("financial", {}).get("fees", {}).get("servicing_fee")

    @property
    def inception(self) -> Optional[date]:
        self._record_access("inception", "dates.origination_date")
        date_str = self._data.get("dates", {}).get("origination_date")
        if date_str:
            return date.fromisoformat(date_str)
        return None

    @property
    def maturity(self) -> Optional[date]:
        self._record_access("maturity", "dates.maturity_date")
        date_str = self._data.get("dates", {}).get("maturity_date")
        if date_str:
            return date.fromisoformat(date_str)
        return None

    @property
    def first_payment(self) -> Optional[date]:
        self._record_access("first_payment", "dates.first_payment_date")
        date_str = self._data.get("dates", {}).get("first_payment_date")
        if date_str:
            return date.fromisoformat(date_str)
        return None

    @property
    def last_modified(self) -> Optional[datetime]:
        self._record_access("last_modified", "dates.last_modified_date")
        date_str = self._data.get("dates", {}).get("last_modified_date")
        if date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return None

    @property
    def status(self) -> str:
        self._record_access("status", "status")
        return self._data.get("status", "")

    @property
    def purpose(self) -> Optional[str]:
        self._record_access("purpose", "loan_type")
        return self._data.get("loan_type")

    @property
    def secured(self) -> bool:
        self._record_access("secured", "collateral_required")
        return self._data.get("collateral_required", False)

    @property
    def payment_frequency(self) -> Optional[str]:
        self._record_access("payment_frequency", "repayment_schedule.frequency")
        return self._data.get("repayment_schedule", {}).get("frequency")

    @property
    def payment_count(self) -> Optional[int]:
        self._record_access("payment_count", "repayment_schedule.number_of_payments")
        return self._data.get("repayment_schedule", {}).get("number_of_payments")

    @property
    def notes(self) -> Optional[str]:
        self._record_access("notes", "notes")
        return self._data.get("notes")

    @property
    def overdue(self) -> bool:
        self._record_access("overdue", "computed.is_overdue")
        if self.maturity:
            return date.today() > self.maturity
        return False

    @property
    def repaid(self) -> float:
        self._record_access("repaid", "computed.utilization_amount")
        return self.principal - self.balance

    @property
    def repayment_pct(self) -> float:
        self._record_access("repayment_pct", "computed.utilization_percentage")
        if self.principal > 0:
            return (self.repaid / self.principal) * 100
        return 0.0

    def __repr__(self) -> str:
        return f"LoanV1(id='{self.id}', principal={self.principal}, currency='{self.currency}')"
