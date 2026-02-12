#!/usr/bin/env python3
"""Run all tests in the tests/ directory and report results."""

import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent / "tests"
TIMEOUT = 30  # seconds per test


def run_test(test_file: Path) -> bool | None:
    """Run a single test file. Returns True (pass), False (fail), or None (skipped)."""
    if test_file.suffix == ".py":
        cmd = [sys.executable, str(test_file)]
    elif test_file.suffix == ".clj":
        cmd = ["bb", str(test_file)]
    else:
        return None

    print(f"\n{'='*70}")
    print(f"  {test_file.name}")
    print(f"{'='*70}\n")

    try:
        result = subprocess.run(cmd, timeout=TIMEOUT)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"\n✗ TIMED OUT after {TIMEOUT}s")
        return False
    except FileNotFoundError as e:
        print(f"\n✗ Could not run: {e}")
        return False


def main():
    test_files = sorted(TESTS_DIR.glob("test_*.*"))
    test_files = [f for f in test_files if f.suffix in (".py", ".clj")]

    results: dict[str, bool] = {}
    for test_file in test_files:
        outcome = run_test(test_file)
        if outcome is not None:
            results[test_file.name] = outcome

    passed = [name for name, ok in results.items() if ok]
    failed = [name for name, ok in results.items() if not ok]

    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}\n")
    for name in passed:
        print(f"  ✓  {name}")
    for name in failed:
        print(f"  ✗  {name}")
    print(f"\n  {len(passed)} passed, {len(failed)} failed\n")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
