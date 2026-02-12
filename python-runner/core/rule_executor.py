import time
from typing import List, Dict, Any
from entity_helpers import create_entity_helper


class RuleExecutor:
    """Executes validation rules hierarchically with timing and dependency management"""

    def __init__(self, rules: List[Any], entity_data: dict, required_data: dict):
        """
        Initialize rule executor.

        Args:
            rules: List of rule objects to execute
            entity_data: The entity being validated
            required_data: Additional data fetched for validation (parent, siblings, etc.)
        """
        self.rules = {r.get_id(): r for r in rules}
        self.entity_data = entity_data
        self.required_data = required_data

        # Determine entity type from first rule
        entity_type = rules[0].validates() if rules else None

        # Create entity helper with domain-aware data abstraction
        if entity_type:
            self.entity_helper = create_entity_helper(
                entity_type,
                entity_data,
                track_access=False
            )
        else:
            self.entity_helper = None

        # Simple cache for entity and required data
        self.cache = {
            "entity": entity_data,
            "required": required_data
        }

    def execute_hierarchical(self, rule_configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute rules respecting hierarchical dependencies.

        Args:
            rule_configs: List of rule config dicts with structure:
                [{"rule_id": "rule_001", "children": [...]}, ...]

        Returns:
            Hierarchical results structure matching config
        """
        results = []
        for config in rule_configs:
            result = self._execute_rule(config)
            results.append(result)
        return results

    def _execute_rule(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single rule and its children."""
        rule_id = config["rule_id"]
        rule = self.rules.get(rule_id)

        if not rule:
            return {
                "rule_id": rule_id,
                "status": "NORUN",
                "message": f"Rule {rule_id} not found",
                "execution_time_ms": 0,
                "children": []
            }

        # Inject entity helper for domain-aware data access
        if self.entity_helper:
            rule.entity = self.entity_helper

        # Provide required data to rule
        rule_required = rule.required_data()
        rule_data = {k: self.required_data.get(k) for k in rule_required}
        rule.set_required_data(rule_data)

        # Execute rule with timing
        start = time.time()
        try:
            status, message = rule.run()
        except Exception as e:
            status = "ERROR"
            message = f"{type(e).__name__}: {e}"
        elapsed_ms = round((time.time() - start) * 1000, 2)

        # Build result
        result = {
            "rule_id": rule_id,
            "description": rule.description(),
            "status": status,
            "message": message,
            "execution_time_ms": elapsed_ms,
            "children": []
        }

        # Execute children only if parent passed
        if status == "PASS" and "children" in config:
            for child_config in config["children"]:
                child_result = self._execute_rule(child_config)
                result["children"].append(child_result)
        elif status in ["FAIL", "NORUN"] and "children" in config:
            # Mark children as NORUN since parent didn't pass
            for child_config in config["children"]:
                result["children"].append(self._mark_skipped(child_config))

        return result

    def _mark_skipped(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Mark a rule and its children as skipped."""
        rule_id = config["rule_id"]
        rule = self.rules.get(rule_id)

        result = {
            "rule_id": rule_id,
            "description": rule.description() if rule else "",
            "status": "NORUN",
            "message": "Parent rule did not pass, rule skipped",
            "execution_time_ms": 0,
            "children": []
        }

        # Recursively mark children
        if "children" in config:
            for child_config in config["children"]:
                result["children"].append(self._mark_skipped(child_config))

        return result
