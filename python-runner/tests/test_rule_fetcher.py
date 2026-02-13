import tempfile
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rule_fetcher import RuleFetcher


def test_fetch_relative_path():
    """Test fetching rule from relative path"""
    # Create a temporary rule file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('class Rule:\n    pass\n')
        rule_path = f.name

    try:
        fetcher = RuleFetcher()
        result_path = fetcher.fetch_rule(rule_path)

        assert result_path.exists()
        assert result_path.read_text() == 'class Rule:\n    pass\n'
        print("✓ Relative path test passed")
    finally:
        Path(rule_path).unlink()


def test_fetch_file_uri():
    """Test fetching rule from file:// URI"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('class Rule:\n    pass\n')
        rule_path = f.name

    try:
        fetcher = RuleFetcher()
        file_uri = f'file://{rule_path}'
        result_path = fetcher.fetch_rule(file_uri)

        assert result_path.exists()
        assert result_path.read_text() == 'class Rule:\n    pass\n'
        print("✓ File URI test passed")
    finally:
        Path(rule_path).unlink()


def test_cache_http_rule():
    """Test caching of HTTP-fetched rule"""
    # Mock urllib.request.urlopen
    rule_content = 'class Rule:\n    def __init__(self, rule_id):\n        pass\n'

    class MockResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return rule_content.encode('utf-8')

    def mock_urlopen(url):
        return MockResponse()

    # Monkey patch urllib.request.urlopen
    import urllib.request
    original_urlopen = urllib.request.urlopen
    urllib.request.urlopen = mock_urlopen

    try:
        fetcher = RuleFetcher()
        uri = 'https://example.com/rules/loan/rule_001_v1.py'

        # First fetch - should cache
        result_path_1 = fetcher.fetch_rule(uri)
        assert result_path_1.exists()
        assert result_path_1.read_text() == rule_content

        # Second fetch - should use cache
        result_path_2 = fetcher.fetch_rule(uri)
        assert result_path_2 == result_path_1  # Same cached file
        print("✓ HTTP caching test passed")
    finally:
        # Restore original urlopen
        urllib.request.urlopen = original_urlopen


if __name__ == "__main__":
    print("="*70)
    print("Testing RuleFetcher")
    print("="*70)

    test_fetch_relative_path()
    test_fetch_file_uri()
    test_cache_http_rule()

    print("\n" + "="*70)
    print("✓ All RuleFetcher tests passed!")
    print("="*70)
