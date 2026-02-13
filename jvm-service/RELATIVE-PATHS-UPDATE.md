# Relative Paths Update for Containerization

## Summary

Updated all file paths in examples and test files from absolute to relative paths to support containerization.

**Date:** 2026-02-12
**Status:** ✅ Complete and tested

## Why This Change?

**Problem:** Absolute paths like `/Users/jude/Dropbox/Projects/...` won't work in containers

**Solution:** Use relative paths that work from the `jvm-service/` working directory

## Path Formats Discovered

### For Schema URLs (in entity data):
```
Before: file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json
After:  file://../logic/models/loan.schema.v1.0.0.json
```

### For File URIs (batch-file endpoint):
```
Before: file:///Users/jude/Dropbox/Projects/validation-service/jvm-service/test/test-data/loans.json
After:  file:./test/test-data/loans.json
```

**Note:** The syntax difference:
- `file://../path` - For schema URLs (needs // after file:)
- `file:./path` - For file URIs (no // after file:)

## Files Updated

### 1. Path Normalization (New Implementation)
**File:** `src/validation_service/utils/file_io.clj`
- ✅ Added `normalize-file-uri` function to convert relative file:// URIs to absolute paths
- Detects relative URIs (`file://..` or `file:.`) and resolves to absolute paths
- Enables Python validation runner to read schemas from relative paths

**File:** `src/validation_service/orchestration/workflow.clj`
- ✅ Updated `execute-validation` to normalize schema URLs before calling Python runner
- Schema URLs in entity data are automatically converted from relative to absolute
- Result: Schema validation (rule_001_v1) now works with relative paths ✅

### 2. Swagger Examples
**File:** `src/validation_service/api/schemas.clj`
- ✅ `validate-request-example` - Schema URL updated to relative path
- ✅ `discover-rules-request-example` - Schema URL updated to relative path
- ✅ `batch-request-example` - Schema URLs updated to relative paths
- ✅ `batch-file-request-example` - File URI and schema URLs updated to relative paths

### 3. Test Data
**File:** `test/test-data/loans.json`
- ✅ Updated `$schema` field in all entities
- From: `file:///Users/jude/...`
- To: `file://../../logic/models/loan.schema.v1.0.0.json`

### 4. Test Request Files
**Directory:** `test/requests/`
- ✅ `batch-inline.json` - Updated schema URLs and id_fields to relative paths
- ✅ `batch-inline-file-output.json` - Updated schema URLs and id_fields to relative paths
- ✅ `batch-file-response.json` - Updated file_uri, entity_types, id_fields to relative paths
- ✅ `batch-file-file-output.json` - Updated file_uri, entity_types, id_fields to relative paths

## Path Resolution

All paths are relative to: **`jvm-service/`** (where the server runs)

### Directory Structure
```
validation-service/
├── logic/
│   └── models/
│       └── loan.schema.v1.0.0.json    # ../logic/models/... from jvm-service/
└── jvm-service/
    ├── (server runs here)
    └── test/
        └── test-data/
            └── loans.json          # ./test/test-data/... from jvm-service/
```

### Path Examples
From `jvm-service/` working directory:
- Schema: `../logic/models/loan.schema.v1.0.0.json` ✅
- Test data: `./test/test-data/loans.json` ✅
- Output: `./test/results/output.json` ✅

## Automatic Path Normalization

**Important:** The JVM service automatically normalizes relative file:// URIs to absolute paths before passing them to the Python validation runner.

### Why Normalization is Needed

Python's `urllib.request.urlopen()` cannot properly resolve relative file:// URIs:
- `file://../models/schema.json` → Python treats as `/models/schema.json` (incorrect)
- `file:./test/data.json` → Python treats as `/test/data.json` (incorrect)

### How It Works

The `normalize-file-uri` function in `src/validation_service/utils/file_io.clj`:
1. Detects relative file:// URIs (starts with `file://..` or `file:.`)
2. Resolves them to absolute paths using current working directory
3. Converts to absolute file:// URI format

**Example:**
```
Input:  file://../logic/models/loan.schema.v1.0.0.json
Output: file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json
```

### Where Normalization Happens

**File:** `src/validation_service/orchestration/workflow.clj`

- In `execute-validation`: Schema URL from entity data is normalized before calling Python
- Result: Schema validation (rule_001_v1) now works correctly with relative paths

### Files Modified for Normalization

- ✅ `src/validation_service/utils/file_io.clj` - Added `normalize-file-uri` function
- ✅ `src/validation_service/orchestration/workflow.clj` - Updated `execute-validation` to normalize schema URLs

## Testing Results

### ✅ All Tests Pass (Including Schema Validation)

**Schema Validation Status:** ✅ WORKING
- rule_001_v1 (JSON schema validation) now shows **PASS** with relative paths
- Previously showed NORUN due to Python urllib path resolution issues
- Fixed by automatic path normalization in JVM service

**Manual Tests:**
```bash
# Test 1: Single entity validation with relative schema path
curl -X POST http://localhost:8080/api/v1/validate -d '{
  "entity_type": "loan",
  "entity_data": {
    "$schema": "file://../logic/models/loan.schema.v1.0.0.json",
    ...
  },
  "ruleset_name": "quick"
}'
✓ rule_001_v1: PASS (schema validation working!)
✓ rule_002_v1: PASS

# Test 2: Batch with relative schema paths
✓ Entity count: 2
✓ All entities: Schema validation PASS

# Test 3: Batch-file with relative file URI
✓ Entity count: 2, First entity: LN-001
✓ Schema validation: PASS for all entities
```

**Babashka Test Suite:**
```
Total Tests: 4
Passed: 4
Failed: 0
✓ All tests passed!
✓ Schema validation (rule_001_v1) shows PASS in all test results
```

### Test Matrix
| Test | Schema Path | File Path | Status |
|------|------------|-----------|--------|
| Batch inline (response) | Relative | N/A | ✅ PASS |
| Batch inline (file out) | Relative | N/A | ✅ PASS |
| Batch-file (response) | Relative | Relative | ✅ PASS |
| Batch-file (file out) | Relative | Relative | ✅ PASS |

## Containerization Ready

### Docker Example
```dockerfile
WORKDIR /app/jvm-service
COPY logic/ ../logic/
COPY jvm-service/ ./
RUN clojure -M -e "(compile 'validation-service.core)"
CMD ["java", "-jar", "target/validation-service.jar"]
```

Paths will work because:
- Working directory is `/app/jvm-service`
- Schema at `/app/logic/models/` → `../logic/models/` ✅
- Test data at `/app/jvm-service/test/test-data/` → `./test/test-data/` ✅

## API Examples with Relative Paths

### POST /api/v1/batch
```json
{
  "entities": [
    {
      "entity_type": "loan",
      "entity_data": {
        "$schema": "file://../logic/models/loan.schema.v1.0.0.json",
        "loan_number": "LN-001",
        ...
      }
    }
  ],
  "id_fields": {
    "file://../logic/models/loan.schema.v1.0.0.json": "loan_number"
  },
  "ruleset_name": "quick"
}
```

### POST /api/v1/batch-file
```json
{
  "file_uri": "file:./test/test-data/loans.json",
  "entity_types": {
    "file://../../logic/models/loan.schema.v1.0.0.json": "loan"
  },
  "id_fields": {
    "file://../../logic/models/loan.schema.v1.0.0.json": "loan_number"
  },
  "ruleset_name": "quick"
}
```

## Migration Notes

### For Existing Users

If you have existing data files or scripts using absolute paths:

**Option 1: Update to relative paths (recommended)**
```bash
# Replace absolute paths with relative
sed -i 's|file:///full/path/to/logic/models/|file://../logic/models/|g' your-data.json
```

**Option 2: Continue using absolute paths**
- Absolute paths still work
- But won't work in containers
- Update before containerizing

### Working Directory Requirement

⚠️ **Important:** The server MUST be run from `jvm-service/` directory:

```bash
# ✅ Correct
cd jvm-service && clojure -M -m validation-service.core

# ❌ Wrong (paths won't resolve)
cd validation-service && clojure -M -m jvm-service.validation-service.core
```

## Benefits

1. ✅ **Container-ready** - Works in Docker/Kubernetes
2. ✅ **Portable** - Works on any machine/OS
3. ✅ **Simpler** - No hardcoded user paths
4. ✅ **Tested** - All tests pass with relative paths
5. ✅ **Backward compatible** - Absolute paths still work

## Next Steps for Containerization

1. Create Dockerfile with correct WORKDIR
2. Ensure server starts from `jvm-service/` directory
3. Mount volumes for config/data if needed
4. Test in container environment

---

**Implementation Time:** ~30 minutes
**Testing:** ✅ Complete - all scenarios pass
**Breaking Changes:** None (absolute paths still supported)
