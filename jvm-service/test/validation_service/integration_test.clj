(ns validation-service.integration-test
  "Manual integration test - run with: clj -M:test -m validation-service.integration-test"
  (:require [clj-http.client :as http]
            [cheshire.core :as json]
            [clojure.pprint :refer [pprint]]))

(defn test-health-endpoint []
  (println "\n=== Testing GET /health ===")
  (let [response (http/get "http://localhost:8080/health"
                          {:as :json})]
    (println "Status:" (:status response))
    (println "Body:")
    (pprint (:body response))
    (assert (= 200 (:status response)) "Health check should return 200")))

(defn test-validate-endpoint []
  (println "\n=== Testing POST /api/v1/validate ===")
  (let [request-body {:entity_type "loan"
                     :entity_data {:$schema "file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json"
                                  :id "LOAN-TEST-001"
                                  :loan_number "LN-001"
                                  :facility_id "FAC-100"
                                  :financial {:principal_amount 100000
                                             :outstanding_balance 75000
                                             :currency "USD"
                                             :interest_rate 0.05}
                                  :dates {:origination_date "2024-01-01"
                                         :maturity_date "2025-01-01"}
                                  :status "active"}
                     :ruleset_name "quick"}
        response (http/post "http://localhost:8080/api/v1/validate"
                           {:body (json/generate-string request-body)
                            :headers {"Content-Type" "application/json"}
                            :as :json})]
    (println "Status:" (:status response))
    (println "Body:")
    (pprint (:body response))
    (assert (= 200 (:status response)) "Validate should return 200")))

(defn test-discover-rules-endpoint []
  (println "\n=== Testing POST /api/v1/discover-rules ===")
  (let [request-body {:entity_type "loan"
                     :entity_data {:$schema "file:///Users/jude/Dropbox/Projects/validation-service/logic/models/loan.schema.v1.0.0.json"
                                  :id "TEST"}
                     :ruleset_name "quick"}
        response (http/post "http://localhost:8080/api/v1/discover-rules"
                           {:body (json/generate-string request-body)
                            :headers {"Content-Type" "application/json"}
                            :as :json})]
    (println "Status:" (:status response))
    (println "Body:")
    (pprint (:body response))
    (assert (= 200 (:status response)) "Discover-rules should return 200")))

(defn -main [& args]
  (println "===== Integration Tests =====")
  (println "Make sure the server is running on http://localhost:8080")

  (try
    (test-health-endpoint)
    (test-validate-endpoint)
    (test-discover-rules-endpoint)
    (println "\n✓ All integration tests passed!")
    (catch Exception e
      (println "\n✗ Test failed:" (.getMessage e))
      (.printStackTrace e)
      (System/exit 1))))
