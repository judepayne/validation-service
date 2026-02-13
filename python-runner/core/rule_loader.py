"""
Rule Loader - Dynamic Rule Discovery and Loading

Discovers and loads validation rule modules from the filesystem using a convention-based
approach that eliminates naming coupling.

## Key Design Principle: Filename as Single Source of Truth

The rule loader uses the filename as the single source of truth for rule identity. There
is no class name derivation algorithm or hardcoded IDs in rule implementations.

Example:
- File: `rules/loan/rule_001_v1.py`
- Contains: `class Rule(ValidationRule)`
- Rule ID: `rule_001_v1` (derived from filename)
- Instantiation: `Rule(rule_id="rule_001_v1")`

## How It Works

1. Config specifies rule_id (e.g., "rule_001_v1")
2. Loader finds matching file across entity type directories (loan/, facility/, deal/)
3. Dynamically imports the module
4. Looks for standard class name "Rule" (not derived names)
5. Instantiates with injected ID: `Rule(rule_id)`
6. Caches the class for performance

This design makes it impossible to have ID/filename/class name mismatches and follows
the DRY principle - the rule ID is specified once in the config, nowhere else.
"""

import importlib.util
from pathlib import Path
from typing import List, Dict, Any


class RuleLoader:
    """Dynamically loads validation rules from filesystem"""

    def __init__(self, config: dict, config_loader=None, rule_fetcher=None):
        """
        Initialize rule loader.

        Args:
            config: Business configuration dict
            config_loader: ConfigLoader instance (optional, for URI resolution)
            rule_fetcher: RuleFetcher instance (optional, for remote rules)
        """
        self.config = config
        self.config_loader = config_loader
        self.rule_fetcher = rule_fetcher
        self.loaded_rules = {}  # Cache: rule_id -> rule_class

        # Backward compatibility: support master_rules_directory
        if 'master_rules_directory' in config:
            self.rules_dir = Path(config['master_rules_directory'])
        else:
            # New mode: rules fetched via URIs
            self.rules_dir = None

    def load_rules(self, rule_configs: List[Dict[str, Any]]) -> List[Any]:
        """
        Load rules from hierarchical configuration.

        Args:
            rule_configs: List of rule config dicts with rule_id and optional children

        Returns:
            List of instantiated rule objects (flattened from hierarchy)
        """
        rules = []
        for config in rule_configs:
            # Add parent rule
            rule_id = config["rule_id"]
            rule = self._load_single_rule(rule_id)
            rules.append(rule)

            # Recursively load children
            if "children" in config:
                child_rules = self.load_rules(config["children"])
                rules.extend(child_rules)

        return rules

    def _load_single_rule(self, rule_id: str, entity_type: str = None) -> Any:
        """
        Load a single rule by ID.

        Args:
            rule_id: Rule identifier (e.g., "rule_001_v1")
            entity_type: Optional entity type hint for faster lookup

        Returns:
            Instantiated rule object

        Raises:
            FileNotFoundError: If rule file doesn't exist
            AttributeError: If rule class not found in module
        """
        # Check cache first
        if rule_id in self.loaded_rules:
            rule_class = self.loaded_rules[rule_id]
            return rule_class(rule_id)

        # Determine if we're in URI mode or path mode
        if self.config_loader and self.rule_fetcher:
            # New mode: resolve URI and fetch
            if not entity_type:
                # Try to infer entity type from rule_id context or search
                entity_type = self._infer_entity_type(rule_id)

            rule_uri = self.config_loader.resolve_rule_uri(entity_type, rule_id)
            rule_path = self.rule_fetcher.fetch_rule(rule_uri)

            # Load module from fetched path
            module_name = f"rules.dynamic.{rule_id}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, rule_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                raise ImportError(
                    f"Failed to import rule {rule_id} from {rule_uri}: {e}"
                )

        else:
            # Backward compat mode: search local rules_dir
            entity_types = ["loan", "facility", "deal"]
            rule_file = None
            searched = []

            for etype in entity_types:
                potential_path = self.rules_dir / etype / f"{rule_id}.py"
                searched.append(str(potential_path))
                if potential_path.exists():
                    rule_file = potential_path
                    entity_type = etype
                    break

            if rule_file is None:
                raise FileNotFoundError(
                    f"Rule file not found: {rule_id}. "
                    f"Searched: {', '.join(searched)}"
                )

            # Load module
            module_name = f"rules.{entity_type}.{rule_id}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, rule_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                raise ImportError(
                    f"Failed to import rule {rule_id} from {rule_file}: {e}"
                )

        # Get rule class (always named "Rule")
        class_name = "Rule"
        if not hasattr(module, class_name):
            raise AttributeError(
                f"Rule class '{class_name}' not found. "
                f"All rules must define a class named 'Rule'."
            )

        rule_class = getattr(module, class_name)

        # Cache the class
        self.loaded_rules[rule_id] = rule_class

        # Return new instance with injected ID
        return rule_class(rule_id)

    def _infer_entity_type(self, rule_id: str) -> str:
        """
        Infer entity type by searching rule configs.

        Looks through all rulesets to find which entity type contains this rule.
        """
        for ruleset_name, ruleset_config in self.config.items():
            if ruleset_name.endswith('_rules'):
                for key, rules_list in ruleset_config.items():
                    if self._rule_in_list(rule_id, rules_list):
                        # Found rule - key might be schema URL or entity type
                        if key.startswith('http'):
                            # Schema URL - default to 'loan' for now
                            # In a real system, we'd map schema to entity type
                            return 'loan'
                        else:
                            return key  # Entity type directly

        # Default fallback
        return 'loan'

    def _rule_in_list(self, rule_id: str, rules_list: list) -> bool:
        """Check if rule_id exists in rules list (including nested children)"""
        for rule in rules_list:
            if rule.get('rule_id') == rule_id:
                return True
            # Check children recursively
            if 'children' in rule:
                if self._rule_in_list(rule_id, rule['children']):
                    return True
        return False

