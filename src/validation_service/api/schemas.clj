(ns validation-service.api.schemas
  "API request and response schemas for validation and documentation."
  (:require [clojure.spec.alpha :as s]))

;; ============================================================================
;; Response Schemas
;; ============================================================================

(s/def ::status #{"PASS" "FAIL" "NORUN" "ERROR"})

(s/def ::health-response
  (s/keys :req-un [::status]))

;; ============================================================================
;; Example Data for Documentation
;; ============================================================================

(def validate-request-example
  {"entity_type" "loan"
   "entity_data" {"$schema" "https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json"
                  "id" "LOAN-12345"
                  "loan_number" "LN-001"
                  "facility_id" "FAC-100"
                  "financial" {"principal_amount" 100000
                               "outstanding_balance" 75000
                               "currency" "USD"
                               "interest_rate" 0.05}
                  "dates" {"origination_date" "2024-01-01"
                           "maturity_date" "2025-01-01"}
                  "status" "active"}
   "ruleset_name" "quick"})

(def discover-rules-request-example
  {"entity_type" "loan"
   "schema_url" "https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json"
   "ruleset_name" "quick"})

(def batch-request-example
  "Example batch validation request with inline entities"
  {"entities"
   [{"entity_type" "loan"
     "entity_data" {"$schema" "https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json"
                    "id" "LOAN-12345"
                    "loan_number" "LN-001"
                    "facility_id" "FAC-100"
                    "financial" {"principal_amount" 100000
                                "outstanding_balance" 75000
                                "currency" "USD"
                                "interest_rate" 0.05}
                    "dates" {"origination_date" "2024-01-01"
                            "maturity_date" "2025-01-01"}
                    "status" "active"}}
    {"entity_type" "loan"
     "entity_data" {"$schema" "https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json"
                    "id" "LOAN-67890"
                    "loan_number" "LN-002"
                    "facility_id" "FAC-100"
                    "financial" {"principal_amount" 50000
                                "outstanding_balance" 25000
                                "currency" "USD"
                                "interest_rate" 0.045}
                    "dates" {"origination_date" "2024-02-01"
                            "maturity_date" "2025-02-01"}
                    "status" "active"}}]
   "id_fields" {"https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json" "loan_number"}
   "ruleset_name" "quick"
   "output_mode" "response"})

(def batch-file-request-example
  "Example batch-file validation request"
  {"file_uri" "file://test-data/loans.json"
   "entity_types" {"https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json" "loan"}
   "id_fields" {"https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json" "loan_number"}
   "ruleset_name" "thorough"
   "output_mode" "file"
   "output_path" "/tmp/validation-results.json"})

(def discover-rulesets-response-example
  "Example discover-rulesets response"
  {"rulesets"
   {"quick"
    {"metadata"
     {"description" "Essential validation checks for real-time inline validation"
      "purpose" "Use during loan origination to catch critical errors before submission"
      "author" "Data Quality Team"
      "date" "2026-02-18"}
     "stats"
     {"total_rules" 2
      "supported_entities" ["loan"]
      "supported_schemas" ["https://bank.example.com/schemas/loan/v1.0.0"
                          "https://bank.example.com/schemas/loan/v2.0.0"]}}
    "thorough"
    {"metadata"
     {"description" "Comprehensive validation checks for complete data quality assurance"
      "purpose" "Use for batch processing and final validation before data publication"
      "author" "Data Quality Team"
      "date" "2026-02-18"}
     "stats"
     {"total_rules" 4
      "supported_entities" ["loan"]
      "supported_schemas" ["https://bank.example.com/schemas/loan/v1.0.0"
                          "https://bank.example.com/schemas/loan/v2.0.0"]}}}
   "timestamp" "2026-02-18T10:30:00Z"
   "total_rulesets" 2})
