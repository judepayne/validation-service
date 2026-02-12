# Test Data Files

This directory contains sample data files for testing batch validation endpoints.

## Files

### loans.json
Sample loan entities for testing `/api/v1/batch-file` endpoint.

**Contents:** 2 loan entities
- **LOAN-12345** (LN-001): $100K principal, 5% rate, matures 2025-01-01
- **LOAN-67890** (LN-002): $50K principal, 4.5% rate, matures 2025-02-01

**Fields:**
- `id` - Entity identifier (required by schema)
- `loan_number` - Loan reference number (used as ID field in batch-file requests)
- `facility_id` - Facility reference
- `financial` - Principal, balance, currency, interest rate
- `dates` - Origination and maturity dates
- `status` - Loan status

**Expected Validation Results:** All rules PASS

## Usage

### From jvm-service directory:

```bash
# Test with response output
curl -X POST http://localhost:8080/api/v1/batch-file \
  -H "Content-Type: application/json" \
  --data-binary @test/requests/batch-file-response.json

# Test with file output
curl -X POST http://localhost:8080/api/v1/batch-file \
  -H "Content-Type: application/json" \
  --data-binary @test/requests/batch-file-file-output.json
```

### Direct curl (without request file):

```bash
curl -X POST http://localhost:8080/api/v1/batch-file \
  -H "Content-Type: application/json" \
  -d '{
    "file_uri": "file:///Users/jude/Dropbox/Projects/validation-service/jvm-service/test/test-data/loans.json",
    "entity_type": "loan",
    "id_field": "loan_number",
    "ruleset_name": "quick",
    "output_mode": "response"
  }'
```

## File Format

Test data files must be JSON arrays of entity objects:

```json
[
  {
    "$schema": "file:///.../loan.schema.v1.0.0.json",
    "id": "LOAN-12345",
    "loan_number": "LN-001",
    ...
  },
  {
    "$schema": "file:///.../loan.schema.v1.0.0.json",
    "id": "LOAN-67890",
    "loan_number": "LN-002",
    ...
  }
]
```

## Creating New Test Files

### Valid Data (PASS scenarios)
1. Create JSON array with entity data objects
2. All entities must be same type for batch-file endpoint
3. Include an ID field (e.g., "loan_number", "deal_id")
4. Include "$schema" in each entity (or just first one - will propagate)
5. Ensure all required schema fields are present
6. Use valid values that pass business rules

### Invalid Data (FAIL scenarios)
Create test files that intentionally violate rules:

**Schema violations:**
```json
{
  "loan_number": "LN-BAD",
  // Missing required "id" field
  "financial": { ... }
}
```

**Business rule violations:**
```json
{
  "id": "LOAN-FAIL",
  "loan_number": "LN-BAD",
  "financial": {
    "principal_amount": -50000,  // Negative principal (should FAIL)
    ...
  }
}
```

**Invalid dates:**
```json
{
  "dates": {
    "origination_date": "2025-01-01",
    "maturity_date": "2024-01-01"  // Maturity before origination (should FAIL)
  }
}
```

## Test Data Maintenance

- Keep files small (< 100 entities) for fast tests
- Document expected validation results in comments
- Use descriptive IDs that indicate test purpose (e.g., "LOAN-NEGATIVE-PRINCIPAL")
- Version test data when schema changes
