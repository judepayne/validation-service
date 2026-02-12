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

    def __init__(self, config: dict):
        """
        Initialize rule loader with configuration.

        Args:
            config: Configuration dict with master_rules_directory and rule definitions
        """
        self.config = config
        self.rules_dir = Path(config.get("master_rules_directory", "./rules"))
        self.loaded_rules = {}  # Cache: rule_id -> rule_class

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

    def _load_single_rule(self, rule_id: str) -> Any:
        """
        Load a single rule by ID.

        Args:
            rule_id: Rule identifier (e.g., "rule_001_v1")

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

        # Determine entity type from rule file location
        # We need to check all entity directories
        entity_types = ["loan", "facility", "deal"]
        rule_file = None
        entity_type = None
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

        # Load module dynamically
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
                f"Rule class '{class_name}' not found in {rule_file}. "
                f"All rules must define a class named 'Rule'."
            )

        rule_class = getattr(module, class_name)

        # Cache the class
        self.loaded_rules[rule_id] = rule_class

        # Return new instance with injected ID
        return rule_class(rule_id)

