"""
Entity helper classes for validation rules.

Provides stable interfaces to entity data (Loan, Facility, Deal) that shield
validation rules from internal data model structure changes.
"""

from .loan_v1 import LoanV1
from .loan_v2 import LoanV2
from .version_registry import get_registry

__all__ = ['LoanV1', 'LoanV2', 'get_registry', 'create_entity_helper']


def create_entity_helper(entity_type: str, entity_data: dict,
                         track_access: bool = False):
    """
    Factory function to create appropriate helper based on entity type and schema version.

    Args:
        entity_type: Type of entity ("loan", "facility", "deal")
        entity_data: Raw entity data as dictionary (may contain $schema field)
        track_access: If True, track which fields are accessed (for discover-rules)

    Returns:
        Entity helper instance (LoanV1, LoanV2, etc.)

    Raises:
        ValueError: If entity_type is not recognized or no helper can be resolved
    """
    import os
    # Auto-initialize registry from default config if not already done
    # entity_helpers lives in logic/, config is at python-runner/local-config.yaml
    default_config = os.path.join(os.path.dirname(__file__), "..", "..", "python-runner", "local-config.yaml")
    registry = get_registry(default_config if os.path.exists(default_config) else None)
    helper_class = registry.get_helper_class(entity_data, entity_type)
    return helper_class(entity_data, track_access=track_access)
