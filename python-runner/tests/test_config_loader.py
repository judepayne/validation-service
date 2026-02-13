import tempfile
import yaml
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_loader import ConfigLoader


def test_load_local_config_only():
    """Test loading config without business_config_uri (backward compat)"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            'quick_rules': {'loan': [{'rule_id': 'rule_001_v1'}]},
            'master_rules_directory': '../rules'
        }, f)
        config_path = f.name

    try:
        loader = ConfigLoader(config_path)
        business_config = loader.get_business_config()

        assert 'quick_rules' in business_config
        assert loader.get_rules_base_uri() is None
        print("✓ Backward compatibility test passed")
    finally:
        Path(config_path).unlink()


def test_load_with_relative_path():
    """Test loading business config from relative path"""
    # Create business config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, dir='/tmp') as f:
        yaml.dump({
            'rules_base_uri': 'https://example.com/rules',
            'quick_rules': {'loan': [{'rule_id': 'rule_001_v1'}]}
        }, f)
        business_config_path = f.name

    # Create local config pointing to business config with relative path
    business_filename = Path(business_config_path).name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, dir='/tmp') as f:
        yaml.dump({
            'business_config_uri': business_filename  # Just the filename (same directory)
        }, f)
        local_config_path = f.name

    try:
        loader = ConfigLoader(local_config_path)

        assert loader.get_rules_base_uri() == 'https://example.com/rules'
        assert 'quick_rules' in loader.get_business_config()
        print("✓ Relative path test passed")
    finally:
        Path(business_config_path).unlink()
        Path(local_config_path).unlink()


def test_load_with_file_uri():
    """Test loading business config from file:// URI"""
    # Create business config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            'rules_base_uri': 'https://example.com/rules',
            'quick_rules': {'loan': [{'rule_id': 'rule_001_v1'}]}
        }, f)
        business_config_path = f.name

    # Create local config pointing to business config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            'business_config_uri': f'file://{business_config_path}'
        }, f)
        local_config_path = f.name

    try:
        loader = ConfigLoader(local_config_path)

        assert loader.get_rules_base_uri() == 'https://example.com/rules'
        assert 'quick_rules' in loader.get_business_config()
        print("✓ File URI test passed")
    finally:
        Path(business_config_path).unlink()
        Path(local_config_path).unlink()


def test_resolve_rule_uri_with_base():
    """Test rule URI resolution with rules_base_uri"""
    # Create business config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            'rules_base_uri': 'https://rules-repo.example.com/v2.1/rules',
            'quick_rules': {}
        }, f)
        business_config_path = f.name

    # Create local config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            'business_config_uri': f'file://{business_config_path}'
        }, f)
        local_config_path = f.name

    try:
        loader = ConfigLoader(local_config_path)
        uri = loader.resolve_rule_uri('loan', 'rule_001_v1')

        assert uri == 'https://rules-repo.example.com/v2.1/rules/loan/rule_001_v1.py'
        print("✓ Rule URI resolution with base test passed")
    finally:
        Path(local_config_path).unlink()
        Path(business_config_path).unlink()


def test_resolve_rule_uri_without_base():
    """Test rule URI resolution without rules_base_uri (relative path)"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            'quick_rules': {'loan': [{'rule_id': 'rule_001_v1'}]}
        }, f)
        config_path = f.name

    try:
        loader = ConfigLoader(config_path)
        uri = loader.resolve_rule_uri('loan', 'rule_001_v1')

        assert uri == '../logic/rules/loan/rule_001_v1.py'
        print("✓ Rule URI resolution without base test passed")
    finally:
        Path(config_path).unlink()


if __name__ == "__main__":
    print("="*70)
    print("Testing ConfigLoader")
    print("="*70)

    test_load_local_config_only()
    test_load_with_relative_path()
    test_load_with_file_uri()
    test_resolve_rule_uri_with_base()
    test_resolve_rule_uri_without_base()

    print("\n" + "="*70)
    print("✓ All ConfigLoader tests passed!")
    print("="*70)
