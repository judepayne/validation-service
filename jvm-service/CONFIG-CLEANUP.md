# Configuration File Cleanup

## Summary

Cleaned up duplicate configuration files and updated documentation to reflect the correct config format.

## Changes Made

### 1. Deleted Unused File
✅ **Removed:** `jvm-service/config.yaml`

**Reason:** The JVM service uses `config.edn` (loaded via Aero library in `src/validation_service/config.clj`). The YAML version was a duplicate with identical content but was never actually loaded by the application.

### 2. Updated Documentation

Updated all references from `config.yaml` to `config.edn` in:

**IMPLEMENTATION-SUMMARY.md:**
- Line 62: "Loads config.yaml" → "Loads config.edn (using Aero)"

**QUICKSTART.md:**
- Line 9: Component description updated
- Line 210: Custom config path example updated
- Lines 214-219: Configuration example changed from YAML to EDN format
- Line 223: Port configuration reference updated

**README.md:**
- Line 38: Custom config path example updated
- Line 70: Directory structure updated
- Line 75: Configuration section updated

## Current Configuration Setup

### JVM Service
- **File:** `config.edn`
- **Format:** EDN (Clojure native)
- **Library:** Aero
- **Location:** `jvm-service/config.edn`
- **Loaded by:** `src/validation_service/config.clj`

### Python Runner
- **File:** `config.yaml`
- **Format:** YAML
- **Library:** PyYAML
- **Location:** `python-runner/config.yaml`
- **Loaded by:** `runner.py`

## Configuration Override

To use a custom config path:

```bash
# JVM Service
java -Dconfig.path=/path/to/config.edn -jar target/*.jar

# Or when running with Clojure
clojure -J-Dconfig.path=/path/to/config.edn -M -m validation-service.core
```

## Config File Format

### config.edn (Current)
```clojure
{:service
 {:port 8080
  :host "0.0.0.0"}

 :python_runner
 {:executable "python3"
  :script_path "../python-runner/runner.py"
  :config_path "../python-runner/config.yaml"}

 ;; ... other settings
}
```

### Why EDN over YAML?

1. **Native Clojure format** - No parsing library needed
2. **Aero library features:**
   - Environment-specific configs
   - Profile support
   - Tag readers for custom types
   - Better integration with Clojure tooling
3. **Type safety** - EDN preserves Clojure data types
4. **Comments** - Better comment syntax for Clojure developers

## Files Not Changed

The following files correctly reference `python-runner/config.yaml` and were **not** changed:
- `TECHNICAL-DESIGN.md` - Documents Python runner config
- `PYTHON-RUNNER-PLAN-TMP.md` - Python runner implementation plan
- `config.edn` itself - Contains path to `../python-runner/config.yaml`

## Verification

All documentation now correctly references:
- ✅ `config.edn` for JVM service configuration
- ✅ `config.yaml` for Python runner configuration (unchanged)

No duplicate configs remaining in `jvm-service/` directory.

---

**Date:** 2026-02-12
**Status:** ✅ Complete
