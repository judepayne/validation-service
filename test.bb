#!/usr/bin/env bb

;; Integration test script for validation-service
;; Tests all main API endpoints with sample data

(require '[babashka.process :as p]
         '[babashka.http-client :as http]
         '[cheshire.core :as json]
         '[clojure.java.io :as io]
         '[clojure.pprint :refer [pprint]])

(def base-url "http://localhost:8080")
(def server-process (atom nil))
(def test-results (atom {:passed 0 :failed 0}))

;; =============================================================================
;; Helpers
;; =============================================================================

(defn log [& args]
  (apply println (str "[" (java.time.LocalTime/now) "]") args))

(defn pass [test-name]
  (swap! test-results update :passed inc)
  (log "✓" test-name))

(defn fail [test-name reason]
  (swap! test-results update :failed inc)
  (log "✗" test-name "-" reason))

(def jar-file "target/validation-service-0.1.0-SNAPSHOT-standalone.jar")

(defn build-jar []
  (log "Checking for uberjar...")
  (when (not (.exists (io/file jar-file)))
    (log "Building uberjar...")
    (let [result @(p/process ["clojure" "-T:build" "uber"]
                             {:out :inherit
                              :err :inherit})]
      (when (not (zero? (:exit result)))
        (log "Failed to build uberjar")
        (System/exit 1))
      (log "Build complete"))))

(defn start-server []
  (build-jar)
  (log "Starting validation-service...")
  (let [proc (p/process ["java" "-jar" jar-file]
                        {:out :inherit
                         :err :inherit})]
    (reset! server-process proc)
    (log "Server process started, waiting for ready...")))

(defn wait-for-server [max-attempts]
  (log "Waiting for server to be ready...")
  (loop [attempt 1]
    (if (> attempt max-attempts)
      (do
        (log "Server failed to start after" max-attempts "attempts")
        false)
      (let [ready? (try
                     (http/get (str base-url "/health"))
                     true
                     (catch Exception e
                       false))]
        (if ready?
          (do
            (log "Server is ready!")
            true)
          (do
            (log "Attempt" attempt "/" max-attempts "- waiting...")
            (Thread/sleep 2000)
            (recur (inc attempt))))))))

(defn stop-server []
  (when @server-process
    (log "Stopping server...")
    (p/destroy @server-process)
    (Thread/sleep 1000)
    (log "Server stopped")))

(defn assert-response [test-name response expected-status expected-keys]
  (try
    (if (not= (:status response) expected-status)
      (do
        (fail test-name (str "Expected status " expected-status ", got " (:status response)))
        false)
      (let [body (if (string? (:body response))
                   (json/parse-string (:body response) true)
                   (:body response))
            missing-keys (filter #(not (contains? body %)) expected-keys)]
        (if (seq missing-keys)
          (do
            (fail test-name (str "Missing expected keys: " missing-keys))
            false)
          (do
            (pass test-name)
            true))))
    (catch Exception e
      (fail test-name (.getMessage e))
      false)))

;; =============================================================================
;; Test Data
;; =============================================================================

(def sample-loan
  {:$schema "https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json"
   :id "LOAN-00001"
   :loan_number "LN-001"
   :facility_id "FAC-100"
   :client_id "CLIENT-001"
   :financial {:principal_amount 100000
               :outstanding_balance 90000
               :currency "USD"
               :interest_rate 0.05
               :interest_type "fixed"}
   :dates {:origination_date "2024-01-01"
           :maturity_date "2029-01-01"
           :first_payment_date "2024-02-01"}
   :status "active"})

;; =============================================================================
;; Tests
;; =============================================================================

(defn test-health-check []
  (log "\n[TEST] Health Check")
  (try
    (let [response (http/get (str base-url "/health"))]
      (if (= (:status response) 200)
        (pass "Health check")
        (fail "Health check" (str "Status: " (:status response)))))
    (catch Exception e
      (fail "Health check" (.getMessage e)))))

(defn test-discover-rulesets []
  (log "\n[TEST] Discover Rulesets")
  (try
    (let [response (http/get (str base-url "/api/v1/discover-rulesets"))
          body (json/parse-string (:body response) true)
          rulesets (:rulesets body)]
      (when (= (:status response) 200)
        (log "Found" (count rulesets) "rulesets:" (keys rulesets))
        (if (and (map? rulesets)
                 (contains? rulesets :quick)
                 (contains? rulesets :thorough))
          (pass "Discover rulesets")
          (fail "Discover rulesets" "Missing expected rulesets"))))
    (catch Exception e
      (fail "Discover rulesets" (.getMessage e)))))

(defn test-discover-rules []
  (log "\n[TEST] Discover Rules")
  (try
    (let [request-body {:entity_type "loan"
                        :schema_url "https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json"
                        :ruleset_name "quick"}
          response (http/post (str base-url "/api/v1/discover-rules")
                              {:headers {"Content-Type" "application/json"}
                               :body (json/generate-string request-body)})
          body (json/parse-string (:body response) true)
          rules (:rules body)]
      (when (= (:status response) 200)
        (log "Found" (count rules) "rules")
        (if (and (coll? rules)
                 (seq rules))
          (pass "Discover rules")
          (fail "Discover rules" "No rules returned"))))
    (catch Exception e
      (fail "Discover rules" (.getMessage e)))))

(defn test-validate []
  (log "\n[TEST] Validate Entity")
  (try
    (let [request-body {:entity_type "loan"
                        :entity_data sample-loan
                        :ruleset_name "quick"}
          response (http/post (str base-url "/api/v1/validate")
                              {:headers {"Content-Type" "application/json"}
                               :body (json/generate-string request-body)})
          body (json/parse-string (:body response) true)
          results (:results body)]  ; API wraps in :results key
      (when (= (:status response) 200)
        (log "Validation results:")
        (doseq [result results]
          (log "  -" (:rule_id result) ":" (:status result)))
        (if (and (vector? results)
                 (seq results)
                 (every? #(contains? % :rule_id) results)
                 (every? #(contains? % :status) results))
          (pass "Validate entity")
          (fail "Validate entity" (str "Invalid response format, got: " (pr-str body))))))
    (catch Exception e
      (fail "Validate entity" (.getMessage e)))))

(defn test-batch-validate []
  (log "\n[TEST] Batch Validate")
  (try
    (let [request-body {:entities [{:entity_type "loan"
                                    :entity_data sample-loan}]
                        :id_fields {"https://raw.githubusercontent.com/judepayne/validation-logic/main/models/loan.schema.v1.0.0.json" "loan_number"}
                        :ruleset_name "quick"}
          response (http/post (str base-url "/api/v1/batch")
                              {:headers {"Content-Type" "application/json"}
                               :body (json/generate-string request-body)})
          body (json/parse-string (:body response) true)
          results (:results body)]  ; API wraps in :results key
      (when (= (:status response) 200)
        (log "Batch validation results for" (count results) "entities")
        (if (and (coll? results)
                 (seq results))
          (pass "Batch validate")
          (fail "Batch validate" (str "Invalid response format, got: " (pr-str body))))))
    (catch Exception e
      (fail "Batch validate" (.getMessage e)))))

;; =============================================================================
;; Main Test Runner
;; =============================================================================

(defn run-tests []
  (println "\n" (str "=" 70))
  (println "Validation Service Integration Tests")
  (println (str "=" 70))

  ;; Start server
  (start-server)

  ;; Wait for server to be ready (30 attempts = ~60 seconds)
  (if (not (wait-for-server 4))
    (do
      (log "Failed to start server, aborting tests")
      (System/exit 1))

    (do
      ;; Run tests
      (test-health-check)
      (test-discover-rulesets)
      (test-discover-rules)
      (test-validate)
      (test-batch-validate)

      ;; Stop server
      (stop-server)

      ;; Print summary
      (println "\n" (str "=" 70))
      (println "Test Summary")
      (println (str "=" 70))
      (println "Passed:" (:passed @test-results))
      (println "Failed:" (:failed @test-results))
      (println (str "=" 70))

      ;; Exit with appropriate code
      (if (zero? (:failed @test-results))
        (do
          (println "✓ All tests passed!")
          (System/exit 0))
        (do
          (println "✗ Some tests failed")
          (System/exit 1))))))

;; Cleanup on exit
(.addShutdownHook (Runtime/getRuntime)
                  (Thread. (fn []
                             (when @server-process
                               (log "Cleanup: stopping server...")
                               (p/destroy @server-process)))))

;; Run tests
(run-tests)
