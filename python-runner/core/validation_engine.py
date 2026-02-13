import sys
import os
import yaml
from pathlib import Path
from typing import List, Dict, Any
from .rule_loader import RuleLoader
from .rule_executor import RuleExecutor
from entity_helpers.version_registry import get_registry
from entity_helpers import create_entity_helper

# Add parent directory to Python path for rules module imports
# This allows rules files to import from rules.base regardless of working directory
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(os.path.dirname(_current_dir))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)


class ValidationEngine:
    """Core validation business logic, independent of transport"""

    def __init__(self, config_path: str):
        """
        Initialize validation engine with two-tier configuration.

        Args:
            config_path: Path to local-config.yaml (tier 1) or config.yaml (legacy)

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is malformed
            ValueError: If config is missing required keys or directories
        """
        from .config_loader import ConfigLoader
        from .rule_fetcher import RuleFetcher

        # Load two-tier config
        cache_dir = os.environ.get('VALIDATION_CACHE_DIR', '/tmp/validation-cache')
        self.config_loader = ConfigLoader(config_path, cache_dir=cache_dir)
        self.config = self.config_loader.get_business_config()

        # Initialize rule fetcher
        self.rule_fetcher = RuleFetcher(cache_dir=f"{cache_dir}/rules")

        # Backward compatibility: support master_rules_directory (deprecated)
        # If no rules_base_uri and no master_rules_directory, assume ../rules
        if 'master_rules_directory' not in self.config and not self.config_loader.get_rules_base_uri():
            self.config['master_rules_directory'] = '../rules'

        # Verify rules directory exists (only for backward compat mode)
        if 'master_rules_directory' in self.config:
            rules_dir = Path(self.config['master_rules_directory'])
            if not rules_dir.exists():
                raise FileNotFoundError(
                    f"Rules directory not found: {rules_dir}. "
                    f"Check 'master_rules_directory' in config"
                )

        # Initialize rule loader with config and fetcher
        self.rule_loader = RuleLoader(self.config, self.config_loader, self.rule_fetcher)

        # Initialize entity helper registry
        get_registry(config_path)

    def get_required_data(self, entity_type: str, schema_url: str, ruleset_name: str) -> List[str]:
        """
        Phase 1: Introspect rules and return required data.

        Returns list of vocabulary terms needed for validation.

        Args:
            entity_type: Type of entity ("loan", "facility", "deal")
            schema_url: The schema URL declaring the entity's version
            ruleset_name: Rule set to use (e.g., "quick", "thorough")

        Returns:
            List of vocabulary terms (e.g., ["parent", "all_siblings"])
        """
        # Load rules based on config and ruleset
        rule_configs = self._get_rules_for_ruleset(entity_type, ruleset_name, schema_url)
        rules = self.rule_loader.load_rules(rule_configs)

        # Collect all required_data from all rules
        required = set()
        for rule in rules:
            required.update(rule.required_data())

        return list(required)

    def validate(self, entity_type: str, entity_data: dict, ruleset_name: str, required_data: dict) -> List[Dict[str, Any]]:
        """
        Phase 2: Execute rules and return hierarchical results.

        Returns structured results matching config hierarchy.

        Args:
            entity_type: Type of entity ("loan", "facility", "deal")
            entity_data: The entity data to validate
            ruleset_name: Rule set to use (e.g., "quick", "thorough")
            required_data: Additional data fetched from coordination service

        Returns:
            List of hierarchical result dicts with structure:
            [{
                "rule_id": str,
                "description": str,
                "status": "PASS" | "FAIL" | "NORUN",
                "message": str,
                "execution_time_ms": int,
                "children": [...]
            }, ...]
        """
        # Load rules
        schema_url = entity_data.get('$schema')
        rule_configs = self._get_rules_for_ruleset(entity_type, ruleset_name, schema_url)
        rules = self.rule_loader.load_rules(rule_configs)

        # Execute with hierarchy
        executor = RuleExecutor(rules, entity_data, required_data)
        results = executor.execute_hierarchical(rule_configs)

        return results

    def discover_rules(
        self,
        entity_type: str,
        entity_data: dict,
        ruleset_name: str
    ) -> Dict[str, Dict]:
        """
        Discover all rules and their comprehensive metadata.

        Args:
            entity_type: Type of entity ("loan", "facility", "deal")
            entity_data: Entity data (used for schema version routing)
            ruleset_name: Rule set to use (e.g., "quick", "thorough")

        Returns:
            Dict mapping rule_id to rule metadata including:
            - rule_id: Unique identifier
            - entity_type: What entity type this rule validates
            - description: Human-readable business purpose
            - required_data: External data vocabulary terms needed
            - field_dependencies: List of (logical, physical) field tuples
            - applicable_schemas: List of schema URLs this rule applies to
        """
        # Get schema URL for routing
        schema_url = entity_data.get('$schema')

        # Load rules for this entity/schema/ruleset
        rule_configs = self._get_rules_for_ruleset(entity_type, ruleset_name, schema_url)
        rules = self.rule_loader.load_rules(rule_configs)

        # Build comprehensive metadata for each rule
        result = {}

        for rule in rules:
            rule_id = rule.get_id()

            # Create entity helper with access tracking
            helper = create_entity_helper(entity_type, entity_data, track_access=True)

            # Execute rule to capture field accesses
            rule.entity = helper
            rule.set_required_data({})
            try:
                rule.run()  # Execute to trigger field accesses
            except:
                pass  # Ignore errors - we only care about field access patterns

            # Collect metadata
            result[rule_id] = {
                "rule_id": rule_id,
                "entity_type": rule.validates(),
                "description": rule.description(),
                "required_data": rule.required_data(),
                "field_dependencies": helper.get_accesses(),
                "applicable_schemas": self._get_applicable_schemas(rule_id, entity_type, ruleset_name)
            }

        return result
    def _get_applicable_schemas(self, rule_id: str, entity_type: str, ruleset_name: str) -> List[str]:
        """
        Find all schema URLs that include this rule.

        Args:
            rule_id: The rule identifier
            entity_type: Entity type
            ruleset_name: Rule set name

        Returns:
            List of schema URLs where this rule is configured
        """
        rules_config = self.config.get(f'{ruleset_name}_rules', {})
        applicable = []

        for key, rule_list in rules_config.items():
            # Check if this is a schema URL (not just entity type)
            if key.startswith("http"):
                # Check if rule_id is in this schema's rule list
                if any(r.get('rule_id') == rule_id for r in rule_list):
                    applicable.append(key)

        return applicable

    def _get_rules_for_ruleset(self, entity_type: str, ruleset_name: str, schema_url: str = None) -> List[Dict[str, Any]]:
        """
        Extract rule configs for given entity type, rule set, and optional schema version.

        Args:
            entity_type: Type of entity ("loan", "facility", "deal")
            ruleset_name: Rule set to use (e.g., "quick", "thorough")
            schema_url: Optional schema URL to get version-specific rules

        Returns:
            List of rule config dicts from config file
        """
        ruleset_key = f"{ruleset_name}_rules"
        rules_config = self.config.get(ruleset_key, {})

        # Try schema_url first (version-specific)
        if schema_url and schema_url in rules_config:
            return rules_config[schema_url]

        # Fallback to entity_type (backward compatibility)
        return rules_config.get(entity_type, [])
