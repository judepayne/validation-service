(ns validation-service.api.schemas
  "API request and response schemas for validation and documentation."
  (:require [clojure.spec.alpha :as s]))

;; ============================================================================
;; Request Schemas
;; ============================================================================

(s/def ::entity-type #{"loan" "facility" "deal"})
(s/def ::ruleset-name #{"quick" "thorough"})
(s/def ::entity-data map?)

(s/def ::validate-request
  (s/keys :req-un [::entity-type ::entity-data ::ruleset-name]))

(s/def ::schema-url string?)

(s/def ::discover-rules-request
  (s/keys :req-un [::entity-type ::schema-url ::ruleset-name]))

;; ============================================================================
;; Response Schemas
;; ============================================================================

(s/def ::rule-id string?)
(s/def ::description string?)
(s/def ::status #{"PASS" "FAIL" "NORUN" "ERROR"})
(s/def ::message string?)
(s/def ::execution-time-ms number?)
(s/def ::children (s/coll-of ::validation-result))

(s/def ::validation-result
  (s/keys :req-un [::rule-id ::description ::status ::message
                   ::execution-time-ms ::children]))

(s/def ::validate-response
  (s/coll-of ::validation-result))

(s/def ::field-dependencies
  (s/coll-of (s/tuple string? string?)))

(s/def ::applicable-schemas
  (s/coll-of string?))

(s/def ::required-data
  (s/coll-of string?))

(s/def ::rule-metadata
  (s/keys :req-un [::rule-id ::entity-type ::description
                   ::required-data ::field-dependencies
                   ::applicable-schemas]))

(s/def ::discover-rules-response
  (s/map-of keyword? ::rule-metadata))

(s/def ::health-response
  (s/keys :req-un [::status]))

;; ============================================================================
;; Example Data for Documentation
;; ============================================================================

(def validate-request-example
  {"entity_type" "loan"
   "entity_data" {"$schema" "file://../models/loan.schema.v1.0.0.json"
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

(def validate-response-example
  [{:rule-id "rule_001_v1"
    :description "Entity data must conform to its declared JSON schema"
    :status "PASS"
    :message ""
    :execution-time-ms 1.2
    :children []}
   {:rule-id "rule_002_v1"
    :description "Loan must have positive principal, valid dates, and non-negative interest rate"
    :status "PASS"
    :message ""
    :execution-time-ms 0.5
    :children []}])

(def discover-rules-request-example
  {"entity_type" "loan"
   "schema_url" "file://../models/loan.schema.v1.0.0.json"
   "ruleset_name" "quick"})

(def discover-rules-response-example
  {:rule_001_v1
   {:rule-id "rule_001_v1"
    :entity-type "loan"
    :description "Entity data must conform to its declared JSON schema"
    :required-data []
    :field-dependencies []
    :applicable-schemas ["https://bank.example.com/schemas/loan/v1.0.0"
                        "https://bank.example.com/schemas/loan/v2.0.0"]}
   :rule_002_v1
   {:rule-id "rule_002_v1"
    :entity-type "loan"
    :description "Loan must have positive principal, valid dates, and non-negative interest rate"
    :required-data []
    :field-dependencies [["principal" "financial.principal-amount"]
                        ["rate" "financial.interest-rate"]
                        ["inception" "dates.origination-date"]
                        ["maturity" "dates.maturity-date"]
                        ["balance" "financial.outstanding-balance"]]
    :applicable-schemas ["https://bank.example.com/schemas/loan/v1.0.0"
                        "https://bank.example.com/schemas/loan/v2.0.0"]}})

(def batch-request-example
  "Example batch validation request with inline entities"
  {"entities"
   [{"entity_type" "loan"
     "entity_data" {"$schema" "file://../models/loan.schema.v1.0.0.json"
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
     "entity_data" {"$schema" "file://../models/loan.schema.v1.0.0.json"
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
   "id_fields" {"file://../models/loan.schema.v1.0.0.json" "loan_number"}
   "ruleset_name" "quick"
   "output_mode" "response"})

(def batch-file-request-example
  "Example batch-file validation request"
  {"file_uri" "file:./test/test-data/loans.json"
   "entity_types" {"file://../../models/loan.schema.v1.0.0.json" "loan"}
   "id_fields" {"file://../../models/loan.schema.v1.0.0.json" "loan_number"}
   "ruleset_name" "thorough"
   "output_mode" "file"
   "output_path" "/tmp/validation-results.json"})
