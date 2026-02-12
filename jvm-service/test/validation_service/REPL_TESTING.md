# REPL Testing Guide

Quick and easy way to test the validation service from the REPL.

## Quick Start

```bash
cd jvm-service
clj -M:dev:repl
```

Then in the REPL:

```clojure
(require '[validation-service.repl-test :as rt])

;; Initialize
(rt/start!)

;; Run a quick test
(rt/test-validate!)

;; See all available functions
(rt/help)

;; Cleanup when done
(rt/stop!)
```

## Available Test Data

Pre-loaded example loan data ready to use:

| Variable | Description |
|----------|-------------|
| `rt/valid-loan` | Valid loan that passes all rules |
| `rt/invalid-loan-negative-principal` | Loan with negative principal (fails validation) |
| `rt/invalid-loan-bad-dates` | Loan with maturity before origination (fails) |
| `rt/paid-off-loan-with-balance` | Paid-off loan with non-zero balance (fails rule_004_v1) |

## Quick Test Functions

### Test Validation

```clojure
;; Test with valid loan
(rt/test-validate!)

;; Test with specific data
(rt/test-validate! rt/invalid-loan-negative-principal)
```

### Test Rule Discovery

```clojure
;; Discover rules in quick ruleset
(rt/test-discover!)

;; Discover rules in thorough ruleset
(rt/test-discover! "thorough")
```

### Run All Tests

```clojure
;; Run complete test suite
(rt/test-all!)
```

## Workflow Functions

### Full Validation Workflow

Mimics what the web service does:

```clojure
(rt/full-validation-workflow "loan" rt/valid-loan "quick")
```

Steps executed:
1. Get schema URL from entity data
2. Call `get-required-data` to discover vocabulary terms needed
3. Call coordination service stub (returns nil, logs call)
4. Call `validate` with entity data + required data
5. Print results and summary

### Individual Pod Calls

```clojure
;; Get required data terms
(rt/get-required-data "loan"
                      "file://.../loan.schema.v1.0.0.json"
                      "quick")
;; Returns: []

;; Validate
(rt/validate "loan"
             rt/valid-loan
             "quick"
             nil)
;; Returns: [{rule results...}]

;; Discover rules
(rt/discover-rules "loan"
                   rt/valid-loan
                   "quick")
;; Returns: {rule-id -> metadata...}
```

## Example REPL Session

```clojure
;; Start
user=> (require '[validation-service.repl-test :as rt])
user=> (rt/start!)
Initializing runner client...
Loading Python runner pod...
✓ Runner client initialized successfully

;; Test valid loan
user=> (rt/test-validate!)

======================================================================
FULL VALIDATION WORKFLOW
======================================================================

Step 1: Get schema URL from entity
  Schema URL: file://.../loan.schema.v1.0.0.json

Step 2: Discover required data terms
=== Calling get-required-data ===
Required data terms: []

Step 3: Fetch required data from coordination service (STUB)
STUB: Coordination service called {:entity-type "loan", ...}
  Coordination service returned: nil

Step 4: Execute validation
=== Calling validate ===
Validation results: [{...}]

Summary:
  Total rules: 4
  Passed: 4
  Failed: 0
  Not run: 0

======================================================================
WORKFLOW COMPLETE
======================================================================

;; Test invalid loan
user=> (rt/test-validate! rt/invalid-loan-negative-principal)
...
Summary:
  Total rules: 4
  Passed: 2
  Failed: 2    ;; Schema + business rule failures
  Not run: 0

;; Discover rules
user=> (rt/test-discover!)

=== Calling discover-rules ===
Discovered 4 rules:

rule_001_v1 :
  Description: Entity data must conform to its declared JSON schema
  Required data: []
  Field dependencies: 0
  Applicable schemas: 2

rule_002_v1 :
  Description: Loan must have positive principal...
  Required data: []
  Field dependencies: 5
  Applicable schemas: 2
...

;; Cleanup
user=> (rt/stop!)
Cleaning up...
✓ Cleanup complete
```

## Testing Different Scenarios

### Valid Data

```clojure
(rt/test-validate! rt/valid-loan)
;; Should pass all rules
```

### Invalid Data - Negative Principal

```clojure
(rt/test-validate! rt/invalid-loan-negative-principal)
;; Should fail:
;; - rule_001_v1 (schema validation)
;; - rule_002_v1 (business logic - positive principal)
```

### Invalid Data - Bad Dates

```clojure
(rt/test-validate! rt/invalid-loan-bad-dates)
;; Should fail:
;; - rule_002_v1 (maturity must be after origination)
```

### Invalid Data - Paid-Off with Balance

```clojure
(rt/test-validate! rt/paid-off-loan-with-balance)
;; Should fail:
;; - rule_004_v1 (paid-off loans must have zero balance)
```

### Different Rulesets

```clojure
;; Quick ruleset (4 rules)
(rt/full-validation-workflow "loan" rt/valid-loan "quick")

;; Thorough ruleset (same 4 rules in this config)
(rt/full-validation-workflow "loan" rt/valid-loan "thorough")
```

## Custom Test Data

Create your own test data:

```clojure
(def my-loan
  {"$schema" "file://.../loan.schema.v1.0.0.json"
   "id" "LOAN-CUSTOM"
   "loan_number" "LN-CUSTOM"
   "facility_id" "FAC-CUSTOM"
   "financial" {"principal_amount" 500000
                "outstanding_balance" 400000
                "currency" "EUR"
                "interest_rate" 0.035}
   "dates" {"origination_date" "2024-06-01"
            "maturity_date" "2027-06-01"}
   "status" "active"})

(rt/test-validate! my-loan)
```

## Troubleshooting

### "Runner client not initialized"

```clojure
;; Make sure to call start! first
(rt/start!)
```

### "Failed to load Python runner pod"

Check that:
1. You're in the `jvm-service` directory
2. Python runner is at `../python-runner/runner.py`
3. Python runner config is at `../python-runner/config.yaml`

### "Configuration file not found"

The test namespace uses relative paths. Make sure you're running from `jvm-service/` directory:

```bash
cd /path/to/validation-service/jvm-service
clj -M:dev:repl
```

## Tips

1. **Use tab completion**: After `(rt/`, press TAB to see all available functions

2. **Re-run tests easily**: Just call the function again:
   ```clojure
   (rt/test-validate!)
   (rt/test-validate!)  ;; Run again
   ```

3. **Pretty-print results**: Results are already pretty-printed with `pprint`

4. **Check logs**: The functions print detailed logs showing each step

5. **Combine functions**: You can call the low-level functions directly:
   ```clojure
   (def terms (rt/get-required-data "loan" schema-url "quick"))
   (def results (rt/validate "loan" my-loan "quick" nil))
   ```

6. **Run everything**: Test all scenarios at once:
   ```clojure
   (rt/test-all!)
   ```

Enjoy testing! 🚀
