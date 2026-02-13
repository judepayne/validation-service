#!/usr/bin/env python3
"""Tests for LogicPackageFetcher."""

import tempfile
import yaml
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logic_fetcher import LogicPackageFetcher


# ── derive_required_files tests ──────────────────────────────────────────

def test_derive_structural_files():
    """Structural files are always included."""
    config = {"quick_rules": {}}
    files = LogicPackageFetcher.derive_required_files(config)

    assert "rules/base.py" in files
    assert "entity_helpers/__init__.py" in files
    assert "entity_helpers/version_registry.py" in files
    print("  pass: structural files always included")


def test_derive_rule_files_from_schema_url():
    """Rule files are derived from schema URL keys in *_rules sections."""
    config = {
        "quick_rules": {
            "https://bank.example.com/schemas/loan/v1.0.0": [
                {"rule_id": "rule_001_v1"},
                {"rule_id": "rule_002_v1"},
            ]
        }
    }
    files = LogicPackageFetcher.derive_required_files(config)

    assert "rules/loan/rule_001_v1.py" in files
    assert "rules/loan/rule_002_v1.py" in files
    print("  pass: rule files derived from schema URL keys")


def test_derive_rule_files_from_entity_type():
    """Rule files are derived from plain entity type keys."""
    config = {
        "quick_rules": {
            "loan": [
                {"rule_id": "rule_001_v1"},
            ]
        }
    }
    files = LogicPackageFetcher.derive_required_files(config)
    assert "rules/loan/rule_001_v1.py" in files
    print("  pass: rule files derived from entity type keys")


def test_derive_rule_files_with_children():
    """Nested children rules are collected recursively."""
    config = {
        "thorough_rules": {
            "loan": [
                {
                    "rule_id": "rule_003_v1",
                    "children": [
                        {"rule_id": "rule_004_v1"}
                    ]
                }
            ]
        }
    }
    files = LogicPackageFetcher.derive_required_files(config)
    assert "rules/loan/rule_003_v1.py" in files
    assert "rules/loan/rule_004_v1.py" in files
    print("  pass: nested children rules collected")


def test_derive_helper_files_from_mapping():
    """Helper files derived from schema_to_helper_mapping."""
    config = {
        "schema_to_helper_mapping": {
            "https://bank.example.com/schemas/loan/v1.0.0": "loan_v1.LoanV1",
            "https://bank.example.com/schemas/loan/v2.0.0": "loan_v2.LoanV2",
        }
    }
    files = LogicPackageFetcher.derive_required_files(config)
    assert "entity_helpers/loan_v1.py" in files
    assert "entity_helpers/loan_v2.py" in files
    print("  pass: helper files from schema_to_helper_mapping")


def test_derive_helper_files_from_defaults():
    """Helper files derived from default_helpers."""
    config = {
        "default_helpers": {
            "loan": "loan_v1.LoanV1",
        }
    }
    files = LogicPackageFetcher.derive_required_files(config)
    assert "entity_helpers/loan_v1.py" in files
    print("  pass: helper files from default_helpers")


def test_derive_deduplicates():
    """Same rule appearing in multiple rulesets is deduplicated."""
    config = {
        "quick_rules": {
            "loan": [{"rule_id": "rule_001_v1"}]
        },
        "thorough_rules": {
            "loan": [{"rule_id": "rule_001_v1"}]
        }
    }
    files = LogicPackageFetcher.derive_required_files(config)
    # Count occurrences — should be exactly 1
    rule_files = [f for f in files if f == "rules/loan/rule_001_v1.py"]
    assert len(rule_files) == 1
    print("  pass: duplicate rules deduplicated")


def test_derive_with_real_business_config():
    """Test with the actual business-config.yaml from the project."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "logic", "business-config.yaml"
    )
    if not os.path.exists(config_path):
        print("  skip: business-config.yaml not found")
        return

    with open(config_path) as f:
        config = yaml.safe_load(f)

    files = LogicPackageFetcher.derive_required_files(config)

    # Verify expected files from the real config
    assert "rules/base.py" in files
    assert "entity_helpers/__init__.py" in files
    assert "entity_helpers/version_registry.py" in files
    assert "rules/loan/rule_001_v1.py" in files
    assert "rules/loan/rule_002_v1.py" in files
    assert "rules/loan/rule_003_v1.py" in files
    assert "rules/loan/rule_004_v1.py" in files
    assert "entity_helpers/loan_v1.py" in files
    assert "entity_helpers/loan_v2.py" in files

    print(f"  pass: real business config yields {len(files)} files: {sorted(files)}")


def test_derive_skips_empty_rules_lists():
    """Empty rule lists (facility: [], deal: []) don't produce files."""
    config = {
        "quick_rules": {
            "facility": [],
            "deal": [],
        }
    }
    files = LogicPackageFetcher.derive_required_files(config)
    # Only structural files should be present
    rule_files = [f for f in files if f.startswith("rules/") and f != "rules/base.py"]
    assert len(rule_files) == 0
    print("  pass: empty rule lists produce no rule files")


# ── extract_entity_type tests ────────────────────────────────────────────

def test_extract_entity_type_from_schema_url():
    """Entity type extracted from schema URL."""
    assert LogicPackageFetcher._extract_entity_type(
        "https://bank.example.com/schemas/loan/v1.0.0") == "loan"
    assert LogicPackageFetcher._extract_entity_type(
        "https://bank.example.com/schemas/facility/v2.1.0") == "facility"
    print("  pass: entity type from schema URL")


def test_extract_entity_type_plain():
    """Plain entity type returned as-is."""
    assert LogicPackageFetcher._extract_entity_type("loan") == "loan"
    assert LogicPackageFetcher._extract_entity_type("facility") == "facility"
    print("  pass: plain entity type")


# ── resolve_logic_dir tests (local) ─────────────────────────────────────

def test_resolve_local_relative_path():
    """Local relative business_config_uri resolves to directory."""
    # Create temp directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create logic/business-config.yaml
        logic_dir = os.path.join(tmpdir, "logic")
        os.makedirs(logic_dir)
        config_path = os.path.join(logic_dir, "business-config.yaml")
        with open(config_path, 'w') as f:
            yaml.dump({"quick_rules": {}}, f)

        # Create python-runner/local-config.yaml pointing to ../logic/
        runner_dir = os.path.join(tmpdir, "python-runner")
        os.makedirs(runner_dir)
        local_config = os.path.join(runner_dir, "local-config.yaml")
        with open(local_config, 'w') as f:
            yaml.dump({"business_config_uri": "../logic/business-config.yaml"}, f)

        fetcher = LogicPackageFetcher()
        result = fetcher.resolve_logic_dir(local_config)

        assert os.path.isabs(result), "Should return absolute path"
        assert result == logic_dir or os.path.samefile(result, logic_dir)
        print(f"  pass: local relative path → {result}")


def test_resolve_no_business_config_uri():
    """Missing business_config_uri returns None (legacy mode)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"quick_rules": {}}, f)
        config_path = f.name

    try:
        fetcher = LogicPackageFetcher()
        result = fetcher.resolve_logic_dir(config_path)
        assert result is None
        print("  pass: no business_config_uri returns None")
    finally:
        os.unlink(config_path)


# ── resolve_logic_dir tests (remote, mocked) ────────────────────────────

def test_resolve_remote_creates_cache():
    """Remote URL fetches files into cache directory structure."""
    business_config = {
        "quick_rules": {
            "loan": [{"rule_id": "rule_001_v1"}]
        },
        "schema_to_helper_mapping": {
            "https://bank.example.com/schemas/loan/v1.0.0": "loan_v1.LoanV1"
        },
        "default_helpers": {
            "loan": "loan_v1.LoanV1"
        }
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create local-config.yaml pointing to remote URL
        local_config = os.path.join(tmpdir, "local-config.yaml")
        with open(local_config, 'w') as f:
            yaml.dump({
                "business_config_uri": "https://example.com/logic/business-config.yaml"
            }, f)

        cache_dir = os.path.join(tmpdir, "cache")
        fetcher = LogicPackageFetcher(cache_dir=cache_dir)

        # Mock _fetch_uri to return appropriate content
        def mock_fetch(uri):
            if uri.endswith("business-config.yaml"):
                return yaml.dump(business_config)
            else:
                return f"# mock content for {uri}"

        with patch.object(fetcher, '_fetch_uri', side_effect=mock_fetch):
            result = fetcher.resolve_logic_dir(local_config)

        # Verify cache structure
        assert os.path.isdir(result)
        assert os.path.exists(os.path.join(result, "business-config.yaml"))
        assert os.path.exists(os.path.join(result, "rules", "base.py"))
        assert os.path.exists(os.path.join(result, "rules", "loan", "rule_001_v1.py"))
        assert os.path.exists(os.path.join(result, "entity_helpers", "__init__.py"))
        assert os.path.exists(os.path.join(result, "entity_helpers", "version_registry.py"))
        assert os.path.exists(os.path.join(result, "entity_helpers", "loan_v1.py"))

        print(f"  pass: remote URL creates cache at {result}")


def test_resolve_remote_fetch_failure_warns():
    """Failed individual file fetch logs warning but doesn't crash."""
    business_config = {
        "quick_rules": {
            "loan": [{"rule_id": "rule_001_v1"}]
        }
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        local_config = os.path.join(tmpdir, "local-config.yaml")
        with open(local_config, 'w') as f:
            yaml.dump({
                "business_config_uri": "https://example.com/logic/business-config.yaml"
            }, f)

        cache_dir = os.path.join(tmpdir, "cache")
        fetcher = LogicPackageFetcher(cache_dir=cache_dir)

        call_count = [0]

        def mock_fetch(uri):
            call_count[0] += 1
            if uri.endswith("business-config.yaml"):
                return yaml.dump(business_config)
            elif "rule_001" in uri:
                raise RuntimeError("Network error")
            return "# content"

        with patch.object(fetcher, '_fetch_uri', side_effect=mock_fetch):
            # Should not raise
            result = fetcher.resolve_logic_dir(local_config)

        assert os.path.isdir(result)
        # rule_001_v1.py should NOT exist (fetch failed)
        assert not os.path.exists(
            os.path.join(result, "rules", "loan", "rule_001_v1.py"))
        print("  pass: failed fetch warns but doesn't crash")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing LogicPackageFetcher")
    print("=" * 70)

    print("\nderive_required_files:")
    test_derive_structural_files()
    test_derive_rule_files_from_schema_url()
    test_derive_rule_files_from_entity_type()
    test_derive_rule_files_with_children()
    test_derive_helper_files_from_mapping()
    test_derive_helper_files_from_defaults()
    test_derive_deduplicates()
    test_derive_with_real_business_config()
    test_derive_skips_empty_rules_lists()

    print("\n_extract_entity_type:")
    test_extract_entity_type_from_schema_url()
    test_extract_entity_type_plain()

    print("\nresolve_logic_dir (local):")
    test_resolve_local_relative_path()
    test_resolve_no_business_config_uri()

    print("\nresolve_logic_dir (remote):")
    test_resolve_remote_creates_cache()
    test_resolve_remote_fetch_failure_warns()

    print("\n" + "=" * 70)
    print("All LogicPackageFetcher tests passed!")
    print("=" * 70)
