#!/usr/bin/env bb
;; Test Python validation runner as a babashka pod

(require '[babashka.pods :as pods])

(println "======================================================================")
(println "Testing Python Validation Runner as Babashka Pod")
(println "======================================================================")

;; Load the Python runner as a pod
(println "\n[1] Loading Python runner as pod...")
(pods/load-pod ["python3" "runner.py" "./local-config.yaml"])
(println "✓ Pod loaded successfully")

;; The pod should expose functions in a namespace
;; Let's try to call them directly via pods/invoke

;; Test 1: get_required_data
(println "\n======================================================================")
(println "Test 1: get_required_data operation")
(println "======================================================================")

(try
  (let [result (pods/invoke "pod.validation-runner" 'get-required-data
                            {:entity_type "loan"
                             :schema_url "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"
                             :ruleset_name "quick"})]
    (println "✓ Result received:" result)
    (println "✓ Required data:" result)
    (assert (vector? result) "Result should be a vector")
    (println "✓ Test 1 PASSED"))
  (catch Exception e
    (println "✗ Test 1 FAILED:" (.getMessage e))
    (println "Stack trace:" e)))

;; Test 2: validate with valid loan
(println "\n======================================================================")
(println "Test 2: validate operation (valid loan)")
(println "======================================================================")

(try
  (let [result (pods/invoke "pod.validation-runner" 'validate
                            {:entity_type "loan"
                             :entity_data {:$schema "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"
                                           :id "LOAN-12345"
                                           :loan_number "LN-001"
                                           :facility_id "FAC-100"
                                           :financial {:principal_amount 250000
                                                      :outstanding_balance 200000
                                                      :currency "USD"
                                                      :interest_rate 0.045}
                                           :dates {:origination_date "2024-06-01"
                                                  :maturity_date "2027-06-01"}
                                           :status "active"}
                             :ruleset_name "quick"
                             :required_data {}})]
    (println "✓ Result received")
    (println "Rules executed:" (count result))
    (doseq [rule-result result]
      (println "  -" (:rule_id rule-result) "→" (:status rule-result)))
    (let [all-passed? (every? #(= "PASS" (:status %)) result)]
      (if all-passed?
        (println "✓ All rules PASSED")
        (println "✗ Some rules failed"))
      (assert all-passed? "All rules should pass for valid loan"))
    (println "✓ Test 2 PASSED"))
  (catch Exception e
    (println "✗ Test 2 FAILED:" (.getMessage e))
    (println "Stack trace:" e)))

;; Test 3: validate with invalid loan
(println "\n======================================================================")
(println "Test 3: validate operation (invalid loan - negative principal)")
(println "======================================================================")

(try
  (let [result (pods/invoke "pod.validation-runner" 'validate
                            {:entity_type "loan"
                             :entity_data {:$schema "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"
                                           :id "LOAN-99999"
                                           :loan_number "LN-002"
                                           :facility_id "FAC-999"
                                           :financial {:principal_amount -50000
                                                      :currency "USD"
                                                      :interest_rate 0.05}
                                           :dates {:origination_date "2024-01-01"
                                                  :maturity_date "2025-01-01"}
                                           :status "active"}
                             :ruleset_name "quick"
                             :required_data {}})]
    (println "✓ Result received")
    (println "Rules executed:" (count result))
    (doseq [rule-result result]
      (println "  -" (:rule_id rule-result) "→" (:status rule-result))
      (when-let [msg (:message rule-result)]
        (when (seq msg)
          (println "    Message:" msg))))
    (let [has-failures? (some #(= "FAIL" (:status %)) result)]
      (if has-failures?
        (println "✓ Rules correctly detected invalid loan")
        (println "✗ No failures detected for invalid loan"))
      (assert has-failures? "Should have failures for invalid loan"))
    (println "✓ Test 3 PASSED"))
  (catch Exception e
    (println "✗ Test 3 FAILED:" (.getMessage e))
    (println "Stack trace:" e)))

(println "\n======================================================================")
(println "✓ All Pod Tests Complete!")
(println "======================================================================")

;; Cleanup: unload the pod
(println "\n[Cleanup] Unloading pod...")
(pods/unload-pod "pod.validation-runner")
(println "✓ Pod unloaded")

(System/exit 0)
