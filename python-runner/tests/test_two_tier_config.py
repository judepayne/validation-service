"""Test two-tier configuration with local-config.yaml and business-config.yaml"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.validation_engine import ValidationEngine


def test_two_tier_config_loading():
    """Test that ValidationEngine can load two-tier config"""
    print("Testing two-tier config loading...")

    # Use local-config.yaml which points to business-config.yaml
    config_path = "local-config.yaml"

    engine = ValidationEngine(config_path)

    # Verify business config was loaded
    assert 'quick_rules' in engine.config
    assert 'thorough_rules' in engine.config
    assert 'schema_to_helper_mapping' in engine.config

    print("✓ Two-tier config loaded successfully")
    print(f"  - Config loader: {engine.config_loader is not None}")
    print(f"  - Rule fetcher: {engine.rule_fetcher is not None}")
    print(f"  - Business config loaded: {len(engine.config)} keys")


def test_rule_loading_with_two_tier_config():
    """Test that rules can be loaded with two-tier config"""
    print("\nTesting rule loading with two-tier config...")

    config_path = "local-config.yaml"
    engine = ValidationEngine(config_path)

    # Test that rules can be discovered
    rule_configs = engine._get_rules_for_ruleset("loan", "quick", None)
    assert len(rule_configs) > 0

    # Test that rules can be loaded
    rules = engine.rule_loader.load_rules(rule_configs)
    assert len(rules) > 0

    print(f"✓ Rules loaded successfully")
    print(f"  - Rule configs found: {len(rule_configs)}")
    print(f"  - Rules loaded: {len(rules)}")


if __name__ == "__main__":
    print("="*70)
    print("Testing Two-Tier Configuration")
    print("="*70)

    test_two_tier_config_loading()
    test_rule_loading_with_two_tier_config()

    print("\n" + "="*70)
    print("✓ All two-tier configuration tests passed!")
    print("="*70)
