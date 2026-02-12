(ns validation-service.repl-test
  "REPL-friendly test namespace with example data and convenience functions.

  Quick start from REPL:
    (require '[validation-service.repl-test :as rt])
    (rt/start!)           ;; Initialize runner client
    (rt/test-validate!)   ;; Run full validation workflow
    (rt/test-discover!)   ;; Discover rules
    (rt/stop!)            ;; Cleanup
  "
  (:require [validation-service.runner.protocol :as proto]
            [validation-service.runner.pods-client :as pods-client]
            [validation-service.orchestration.coordination :as coord]
            [clojure.pprint :refer [pprint]]))

;; ============================================================================
;; Example Test Data
;; ============================================================================

(def config
  "Test configuration"
  {:python_runner {:executable "python3"
                   :script_path "../python-runner/runner.py"
                   :config_path "../python-runner/config.yaml"}
   :coordination_service {:base_url "http://localhost:8081"}})

(def valid-loan
  "Example valid loan data"
  {"$schema" "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"
   "id" "LOAN-12345"
   "loan_number" "LN-001"
   "facility_id" "FAC-100"
   "financial" {"principal_amount" 100000
                "outstanding_balance" 75000
                "currency" "USD"
                "interest_rate" 0.05}
   "dates" {"origination_date" "2024-01-01"
            "maturity_date" "2025-01-01"}
   "status" "active"})

(def invalid-loan-negative-principal
  "Example loan with negative principal (should fail validation)"
  {"$schema" "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"
   "id" "LOAN-99999"
   "loan_number" "LN-BAD"
   "facility_id" "FAC-999"
   "financial" {"principal_amount" -50000
                "outstanding_balance" 0
                "currency" "USD"
                "interest_rate" 0.05}
   "dates" {"origination_date" "2024-01-01"
            "maturity_date" "2025-01-01"}
   "status" "active"})

(def invalid-loan-bad-dates
  "Example loan with maturity before origination (should fail validation)"
  {"$schema" "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"
   "id" "LOAN-88888"
   "loan_number" "LN-DATES"
   "facility_id" "FAC-888"
   "financial" {"principal_amount" 100000
                "outstanding_balance" 75000
                "currency" "USD"
                "interest_rate" 0.05}
   "dates" {"origination_date" "2025-01-01"
            "maturity_date" "2024-01-01"}  ;; Maturity before origination!
   "status" "active"})

(def paid-off-loan-with-balance
  "Example paid-off loan that still has balance (should fail rule_004_v1)"
  {"$schema" "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"
   "id" "LOAN-77777"
   "loan_number" "LN-PAIDOFF"
   "facility_id" "FAC-777"
   "financial" {"principal_amount" 100000
                "outstanding_balance" 5000  ;; Should be 0!
                "currency" "USD"
                "interest_rate" 0.05}
   "dates" {"origination_date" "2024-01-01"
            "maturity_date" "2025-01-01"}
   "status" "paid_off"})

;; ============================================================================
;; State Management
;; ============================================================================

(defonce ^:private state (atom {:runner-client nil}))

(defn start!
  "Initialize the runner client. Call this first!"
  []
  (println "Initializing runner client...")
  (try
    (let [client (pods-client/create-pods-client config)]
      (swap! state assoc :runner-client client)
      (println "✓ Runner client initialized successfully")
      client)
    (catch Exception e
      (println "✗ Failed to initialize runner client:")
      (println (.getMessage e))
      (throw e))))

(defn stop!
  "Cleanup resources"
  []
  (println "Cleaning up...")
  (swap! state assoc :runner-client nil)
  (println "✓ Cleanup complete"))

(defn runner-client
  "Get the current runner client (initialize if needed)"
  []
  (or (:runner-client @state)
      (start!)))

;; ============================================================================
;; Convenience Functions
;; ============================================================================

(defn get-required-data
  "Call pod get-required-data function.

  Args:
    entity-type - 'loan', 'facility', 'deal'
    schema-url - Schema URL from entity data
    ruleset-name - 'quick', 'thorough', etc.

  Returns:
    Vector of vocabulary term strings"
  [entity-type schema-url ruleset-name]
  (println "\n=== Calling get-required-data ===")
  (println "Entity type:" entity-type)
  (println "Schema URL:" schema-url)
  (println "Ruleset:" ruleset-name)
  (let [result (proto/get-required-data (runner-client)
                                        entity-type
                                        schema-url
                                        ruleset-name)]
    (println "\nRequired data terms:")
    (pprint result)
    result))

(defn validate
  "Call pod validate function.

  Args:
    entity-type - 'loan', 'facility', 'deal'
    entity-data - Entity data map
    ruleset-name - 'quick', 'thorough', etc.
    required-data - Map of required data (from coordination service)

  Returns:
    Vector of validation results"
  [entity-type entity-data ruleset-name required-data]
  (println "\n=== Calling validate ===")
  (println "Entity type:" entity-type)
  (println "Entity ID:" (get entity-data "id"))
  (println "Ruleset:" ruleset-name)
  (let [result (proto/validate (runner-client)
                               entity-type
                               entity-data
                               ruleset-name
                               required-data)]
    (println "\nValidation results:")
    (pprint result)
    (println "\nSummary:")
    (let [total (count result)
          passed (count (filter #(= "PASS" (get % "status")) result))
          failed (count (filter #(= "FAIL" (get % "status")) result))
          norun (count (filter #(= "NORUN" (get % "status")) result))]
      (println "  Total rules:" total)
      (println "  Passed:" passed)
      (println "  Failed:" failed)
      (println "  Not run:" norun))
    result))

(defn discover-rules
  "Call pod discover-rules function.

  Args:
    entity-type - 'loan', 'facility', 'deal'
    entity-data - Entity data (used for schema version routing)
    ruleset-name - 'quick', 'thorough', etc.

  Returns:
    Map of rule-id to metadata"
  [entity-type entity-data ruleset-name]
  (println "\n=== Calling discover-rules ===")
  (println "Entity type:" entity-type)
  (println "Ruleset:" ruleset-name)
  (let [result (proto/discover-rules (runner-client)
                                     entity-type
                                     entity-data
                                     ruleset-name)]
    (println "\nDiscovered" (count result) "rules:")
    (doseq [[rule-id metadata] result]
      (println "\n" rule-id ":")
      (println "  Description:" (:description metadata))
      (println "  Required data:" (:required_data metadata))
      (println "  Field dependencies:" (count (:field_dependencies metadata [])) "fields")
      (when-let [deps (seq (:field_dependencies metadata))]
        (doseq [[logical physical] deps]
          (println "    -" logical "→" physical)))
      (println "  Applicable schemas:" (count (:applicable_schemas metadata [])) "versions")
      (when-let [schemas (seq (:applicable_schemas metadata))]
        (doseq [schema schemas]
          (println "    -" schema))))
    result))

;; ============================================================================
;; Workflow Functions (mimics what the web service does)
;; ============================================================================

(defn full-validation-workflow
  "Execute the full validation workflow (same as web service).

  Steps:
  1. Get required data terms from runner
  2. Fetch required data from coordination service (stub returns nil)
  3. Validate with entity data + required data

  Args:
    entity-type - 'loan', 'facility', 'deal'
    entity-data - Entity data map to validate
    ruleset-name - 'quick', 'thorough', etc.

  Returns:
    Validation results"
  [entity-type entity-data ruleset-name]
  (println "\n" (apply str (repeat 70 "=")))
  (println "FULL VALIDATION WORKFLOW")
  (println (apply str (repeat 70 "=")))

  ;; Step 1: Get schema URL from entity data
  (let [schema-url (get entity-data "$schema")]
    (println "\nStep 1: Get schema URL from entity")
    (println "  Schema URL:" schema-url)

    ;; Step 2: Discover required data vocabulary terms
    (println "\nStep 2: Discover required data terms")
    (let [vocabulary-terms (get-required-data entity-type schema-url ruleset-name)]

      ;; Step 3: Fetch required data from coordination service
      (println "\nStep 3: Fetch required data from coordination service (STUB)")
      (let [required-data (coord/fetch-required-data config entity-type vocabulary-terms)]
        (println "  Coordination service returned:" required-data)

        ;; Step 4: Execute validation
        (println "\nStep 4: Execute validation")
        (let [results (validate entity-type entity-data ruleset-name required-data)]
          (println "\n" (apply str (repeat 70 "=")))
          (println "WORKFLOW COMPLETE")
          (println (apply str (repeat 70 "=")))
          results)))))

;; ============================================================================
;; Quick Test Functions
;; ============================================================================

(defn test-validate!
  "Quick test: Validate a valid loan with the full workflow.

  Usage:
    (test-validate!)                    ;; Use default valid-loan
    (test-validate! invalid-loan-negative-principal)  ;; Test with invalid data
  "
  ([]
   (test-validate! valid-loan))
  ([entity-data]
   (full-validation-workflow "loan" entity-data "quick")))

(defn test-discover!
  "Quick test: Discover rules for loan entity.

  Usage:
    (test-discover!)                    ;; Use quick ruleset
    (test-discover! \"thorough\")       ;; Use thorough ruleset
  "
  ([]
   (test-discover! "quick"))
  ([ruleset-name]
   (discover-rules "loan" valid-loan ruleset-name)))

(defn test-all!
  "Run all test scenarios.

  Tests:
  1. Valid loan (should PASS all rules)
  2. Invalid loan - negative principal (should FAIL)
  3. Invalid loan - bad dates (should FAIL)
  4. Paid-off loan with balance (should FAIL rule_004_v1)
  5. Discover rules (quick ruleset)
  6. Discover rules (thorough ruleset)
  "
  []
  (println "\n" (apply str (repeat 80 "=")))
  (println "RUNNING ALL TEST SCENARIOS")
  (println (apply str (repeat 80 "=")))

  ;; Test 1
  (println "\n\n### TEST 1: Valid Loan ###")
  (test-validate! valid-loan)

  ;; Test 2
  (println "\n\n### TEST 2: Invalid Loan - Negative Principal ###")
  (test-validate! invalid-loan-negative-principal)

  ;; Test 3
  (println "\n\n### TEST 3: Invalid Loan - Bad Dates ###")
  (test-validate! invalid-loan-bad-dates)

  ;; Test 4
  (println "\n\n### TEST 4: Paid-Off Loan with Balance ###")
  (test-validate! paid-off-loan-with-balance)

  ;; Test 5
  (println "\n\n### TEST 5: Discover Rules - Quick ###")
  (test-discover! "quick")

  ;; Test 6
  (println "\n\n### TEST 6: Discover Rules - Thorough ###")
  (test-discover! "thorough")

  (println "\n" (apply str (repeat 80 "=")))
  (println "ALL TESTS COMPLETE")
  (println (apply str (repeat 80 "="))))

;; ============================================================================
;; REPL Helpers
;; ============================================================================

(defn help
  "Show available functions and usage examples"
  []
  (println "
=== Validation Service REPL Test Helpers ===

QUICK START:
  (require '[validation-service.repl-test :as rt])
  (rt/start!)           ;; Initialize runner client
  (rt/test-validate!)   ;; Run full validation workflow
  (rt/test-discover!)   ;; Discover rules
  (rt/stop!)            ;; Cleanup

TEST DATA AVAILABLE:
  rt/valid-loan                        ;; Valid loan data
  rt/invalid-loan-negative-principal   ;; Loan with negative amount
  rt/invalid-loan-bad-dates            ;; Loan with maturity < origination
  rt/paid-off-loan-with-balance        ;; Paid-off loan with non-zero balance

CORE FUNCTIONS:
  (rt/get-required-data entity-type schema-url ruleset-name)
    - Get required data vocabulary terms

  (rt/validate entity-type entity-data ruleset-name required-data)
    - Execute validation rules

  (rt/discover-rules entity-type entity-data ruleset-name)
    - Get rule metadata

WORKFLOW FUNCTIONS:
  (rt/full-validation-workflow entity-type entity-data ruleset-name)
    - Execute complete workflow (get-required-data → coordination → validate)

QUICK TESTS:
  (rt/test-validate!)                  ;; Validate valid loan
  (rt/test-validate! rt/invalid-loan-negative-principal)  ;; Test with invalid data
  (rt/test-discover!)                  ;; Discover rules (quick)
  (rt/test-discover! \"thorough\")     ;; Discover rules (thorough)
  (rt/test-all!)                       ;; Run all test scenarios

EXAMPLES:
  ;; Test validation workflow with valid data
  (rt/test-validate!)

  ;; Test with invalid data
  (rt/test-validate! rt/invalid-loan-negative-principal)

  ;; Discover rules for thorough ruleset
  (rt/test-discover! \"thorough\")

  ;; Custom validation
  (rt/full-validation-workflow \"loan\" rt/valid-loan \"quick\")

  ;; Run all tests
  (rt/test-all!)
"))

(comment
  ;; Example REPL session:

  ;; Start the runner client
  (start!)

  ;; Test with valid loan
  (test-validate!)

  ;; Test with invalid loan
  (test-validate! invalid-loan-negative-principal)

  ;; Discover rules
  (test-discover!)
  (test-discover! "thorough")

  ;; Run all tests
  (test-all!)

  ;; Cleanup
  (stop!)

  ;; Or just:
  (help)
  )
