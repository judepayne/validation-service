# Validation Service - Test Suite

This directory contains all test files and scripts for the validation service batch endpoints.

## Directory Structure

```
test/
├── README.md              # This file
├── test-data/            # Input data files
│   ├── loans.json        # Sample loan entities
│   └── README.md         # Test data documentation
├── requests/             # Sample API request files
│   ├── batch-inline.json                 # Batch with inline entities (response mode)
│   ├── batch-inline-file-output.json     # Batch with inline entities (file output mode)
│   ├── batch-file-response.json          # Batch-file from URI (response mode)
│   └── batch-file-file-output.json       # Batch-file from URI (file output mode)
├── results/              # Test output files (generated during tests)
│   ├── batch-inline-output.json          # Output from inline batch (file mode)
│   └── batch-file-output.json            # Output from batch-file (file mode)
└── babashka/             # Test automation scripts
    └── run-tests.clj     # Babashka script to run all tests
```

## Quick Start

### 1. Start the Server

```bash
cd jvm-service
clojure -M -m validation-service.core
```

Wait for: `Server started successfully`

### 2. Run All Tests (Babashka)

```bash
cd jvm-service
./test/babashka/run-tests.clj
```

### 3. Run Individual Tests (curl)

```bash
cd jvm-service

# Test 1: Batch inline - response mode
curl -X POST http://localhost:8080/api/v1/batch \
  -H "Content-Type: application/json" \
  --data-binary @test/requests/batch-inline.json | jq .

# Test 2: Batch inline - file output mode
curl -X POST http://localhost:8080/api/v1/batch \
  -H "Content-Type: application/json" \
  --data-binary @test/requests/batch-inline-file-output.json | jq .

# Test 3: Batch-file - response mode
curl -X POST http://localhost:8080/api/v1/batch-file \
  -H "Content-Type: application/json" \
  --data-binary @test/requests/batch-file-response.json | jq .

# Test 4: Batch-file - file output mode
curl -X POST http://localhost:8080/api/v1/batch-file \
  -H "Content-Type: application/json" \
  --data-binary @test/requests/batch-file-file-output.json | jq .
```

## Test Coverage

### Endpoints Tested
- ✅ `POST /api/v1/batch` - Batch validation with inline entities
- ✅ `POST /api/v1/batch-file` - Batch validation from file URI

### Output Modes Tested
- ✅ Response mode - Results returned in HTTP response
- ✅ File mode - Results written to file

### Scenarios Tested
- ✅ Multiple entities (2 loans)
- ✅ Schema validation (rule_001_v1)
- ✅ Business rule validation (rule_002_v1)
- ✅ ID field extraction (loan_number)
- ✅ File URI loading (file://)
- ✅ Overall batch statistics

## Test Data

### loans.json
Contains 2 valid loan entities:
- **LOAN-12345** (LN-001): $100K principal, 5% rate
- **LOAN-67890** (LN-002): $50K principal, 4.5% rate

Both loans should pass all validation rules.

## Expected Results

### Successful Validation
```json
{
  "batch_id": "BATCH-2026-02-12-142341",
  "entity_count": 2,
  "overall_summary": {
    "total_entities": 2,
    "completed": 2,
    "errors": 0,
    "entities_with_failures": 0
  }
}
```

### Each Entity Result
```json
{
  "entity_type": "loan",
  "entity_id": "LN-001",
  "status": "completed",
  "results": [
    {
      "rule_id": "rule_001_v1",
      "status": "PASS",
      ...
    },
    {
      "rule_id": "rule_002_v1",
      "status": "PASS",
      ...
    }
  ]
}
```

## Modifying Tests

### Adding New Test Data
1. Create JSON file in `test/test-data/`
2. Create request file in `test/requests/` referencing new data
3. Update `babashka/run-tests.clj` to include new test
4. Run tests to verify

### Creating Failure Scenarios
To test validation failures, modify test data:

```json
{
  "financial": {
    "principal_amount": -50000,  // Negative principal (should fail)
    ...
  }
}
```

## Viewing Results

### Response Mode Results
Results are displayed in terminal output (pipe through `jq` for formatting).

### File Mode Results
```bash
# View inline batch output
cat test/results/batch-inline-output.json | jq .

# View batch-file output
cat test/results/batch-file-output.json | jq .
```

## Troubleshooting

### Server Not Running
```
Error: Failed to connect to localhost:8080
Solution: Start the server first (see Quick Start step 1)
```

### File Not Found Errors
```
Error: Failed to fetch input file
Solution: Ensure all paths in request files are absolute and correct
```

### Permission Denied on Results
```
Error: Failed to write output file
Solution: Ensure results/ directory exists and is writable
```

## Integration with CI/CD

The babashka test script returns exit codes:
- `0` - All tests passed
- `1` - One or more tests failed

Use in CI/CD pipeline:
```bash
#!/bin/bash
# Start server in background
clojure -M -m validation-service.core &
SERVER_PID=$!

# Wait for server to start
sleep 10

# Run tests
./test/babashka/run-tests.clj
TEST_RESULT=$?

# Cleanup
kill $SERVER_PID

exit $TEST_RESULT
```

## Next Steps

1. **Add more test scenarios**:
   - Invalid data (schema violations)
   - Mixed entity types (batch only)
   - Large batches (performance testing)
   - HTTP/HTTPS file URIs

2. **Add unit tests**:
   - Test file I/O utilities
   - Test workflow functions
   - Test handler error cases

3. **Performance benchmarks**:
   - Measure throughput (entities/second)
   - Measure latency (p50, p95, p99)
   - Test with large files (1K, 10K, 100K entities)

## Related Documentation

- `../curl.txt` - Additional curl examples
- `test-data/README.md` - Test data documentation
- `../../BATCH-VALIDATION-IMPLEMENTATION.md` - Implementation details
