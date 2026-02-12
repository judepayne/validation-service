#!/usr/bin/env bb
;; Babashka script to run batch validation tests

(require '[babashka.curl :as curl]
         '[cheshire.core :as json]
         '[clojure.java.io :as io])

(def base-url "http://localhost:8080")
(def test-dir (io/file (System/getProperty "user.dir") "test"))
(def results-dir (io/file test-dir "results"))

(defn ensure-results-dir []
  (when-not (.exists results-dir)
    (.mkdirs results-dir))
  (println "Results directory:" (.getAbsolutePath results-dir)))

(defn load-request [filename]
  (let [file (io/file test-dir "requests" filename)]
    (json/parse-string (slurp file))))

(defn make-request [endpoint request-file]
  (println "\n" (str "Testing " endpoint " with " request-file))
  (println "=" (apply str (repeat 60 "=")))
  (try
    (let [request-data (load-request request-file)
          response (curl/post (str base-url endpoint)
                              {:headers {"Content-Type" "application/json"}
                               :body (json/generate-string request-data)
                               :throw false})
          status (:status response)
          body (json/parse-string (:body response) true)]

      (println "Status:" status)

      (if (= 200 status)
        (do
          (println "✓ Success")
          (when-let [batch-id (:batch_id body)]
            (println "  Batch ID:" batch-id))
          (when-let [entity-count (:entity_count body)]
            (println "  Entity Count:" entity-count))
          (when-let [output-path (:output_path body)]
            (println "  Output File:" output-path))
          (when-let [summary (:overall_summary body)]
            (println "  Summary:" summary))
          {:success true :response body})
        (do
          (println "✗ Failed")
          (println "  Error:" (:error body))
          {:success false :response body})))
    (catch Exception e
      (println "✗ Exception:" (.getMessage e))
      {:success false :error (.getMessage e)})))

(defn run-all-tests []
  (ensure-results-dir)

  (println "\n" "BATCH VALIDATION TEST SUITE")
  (println "=" (apply str (repeat 60 "=")))

  (let [tests [
               ;; Batch inline tests
               {:name "Batch Inline - Response Mode"
                :endpoint "/api/v1/batch"
                :request "batch-inline.json"}

               {:name "Batch Inline - File Output Mode"
                :endpoint "/api/v1/batch"
                :request "batch-inline-file-output.json"}

               ;; Batch file tests
               {:name "Batch File - Response Mode"
                :endpoint "/api/v1/batch-file"
                :request "batch-file-response.json"}

               {:name "Batch File - File Output Mode"
                :endpoint "/api/v1/batch-file"
                :request "batch-file-file-output.json"}]

        results (map (fn [{:keys [name endpoint request]}]
                      (println "\n" (str "TEST: " name))
                      (assoc (make-request endpoint request)
                             :test-name name))
                    tests)

        total (count results)
        passed (count (filter :success results))
        failed (- total passed)]

    (println "\n\n" "TEST SUMMARY")
    (println "=" (apply str (repeat 60 "=")))
    (println "Total Tests:" total)
    (println "Passed:" passed)
    (println "Failed:" failed)

    (when (pos? failed)
      (println "\nFailed Tests:")
      (doseq [{:keys [test-name]} (filter (complement :success) results)]
        (println "  ✗" test-name)))

    (if (zero? failed)
      (do
        (println "\n✓ All tests passed!")
        (System/exit 0))
      (do
        (println "\n✗ Some tests failed")
        (System/exit 1)))))

;; Main execution
(when (= *file* (System/getProperty "babashka.file"))
  (println "Starting validation service tests...")
  (println "Make sure the server is running on" base-url)
  (Thread/sleep 1000)
  (run-all-tests))
