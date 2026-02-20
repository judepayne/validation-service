(ns validation-service.api.handlers
  (:require [validation-service.client.lifecycle :as client]
            [validation-service.utils.file-io :as file-io]
            [clojure.tools.logging :as log])
  (:import [java.time Instant LocalDateTime]
           [java.time.format DateTimeFormatter]))

(defn- json-response
  "Create JSON response map.

  The wrap-json-response middleware will serialize the :body to JSON."
  [status body]
  {:status status
   :headers {"Content-Type" "application/json"}
   :body body})

(defn- error-response
  "Create detailed error response.

  Args:
    status - HTTP status code
    message - Error message
    error-type - Error type keyword (:validation-error, :pod-communication-error, etc.)
    details - Optional additional error details map

  Returns:
    Ring response map"
  [status message error-type & [details]]
  (json-response status
                 {:error message
                  :error_type (name error-type)
                  :timestamp (.toString (Instant/now))
                  :details (or details {})}))

(defn validate-handler
  "Handle POST /api/v1/validate requests.

  Request body (from wrap-json-body middleware):
  {
    \"entity_type\": \"loan\",
    \"entity_data\": {...},
    \"ruleset_name\": \"quick\"  (optional, defaults to \"quick\")
  }

  Returns hierarchical validation results."
  [{:keys [body] :as request}]
  (let [entity-type (get body "entity_type")
        entity-data (get body "entity_data")
        ruleset-name (get body "ruleset_name" "quick")]

    (log/info "Received validation request"
              {:entity-type entity-type
               :ruleset ruleset-name
               :entity-id (get entity-data "id")})

    (try
      (let [results (client/validate entity-type
                                     entity-data
                                     ruleset-name)
            ;; Build summary
            total (count results)
            passed (count (filter #(= "PASS" (get % "status")) results))
            failed (count (filter #(= "FAIL" (get % "status")) results))
            norun (count (filter #(= "NORUN" (get % "status")) results))]

        (json-response 200
                      {:entity_type entity-type
                       :entity_id (get entity-data "id")
                       :timestamp (.toString (Instant/now))
                       :ruleset ruleset-name
                       :results results
                       :summary {:total_rules total
                                :passed passed
                                :failed failed
                                :not_run norun
                                :total_time_ms (reduce + (map #(get % "execution_time_ms" 0) results))}}))

      (catch clojure.lang.ExceptionInfo e
        (let [data (ex-data e)]
          (log/error e "Validation request failed" data)
          (case (:type data)
            :pod-communication-error
            (error-response 503
                           "Failed to communicate with validation runner"
                           :pod-communication-error
                           data)

            ;; Default error
            (error-response 500
                           (.getMessage e)
                           :internal-error
                           data))))

      (catch Exception e
        (log/error e "Unexpected error in validation handler")
        (error-response 500
                       "Internal server error"
                       :internal-error
                       {:message (.getMessage e)})))))

(defn discover-rules-handler
  "Handle POST /api/v1/discover-rules requests.

  Request body:
  {
    \"entity_type\": \"loan\",
    \"schema_url\": \"file:///.../loan.schema.v1.0.0.json\",
    \"ruleset_name\": \"quick\"
  }

  Returns comprehensive rule metadata."
  [{:keys [body] :as request}]
  (let [entity-type (get body "entity_type")
        schema-url (get body "schema_url")
        ruleset-name (get body "ruleset_name" "quick")
        ;; Create minimal entity data with schema for discovery
        entity-data {"$schema" schema-url}]

    (log/info "Received discover-rules request"
              {:entity-type entity-type
               :schema-url schema-url
               :ruleset ruleset-name})

    (try
      (let [rules (client/discover-rules entity-type
                                         entity-data
                                         ruleset-name)]

        (json-response 200
                      {:entity_type entity-type
                       :schema_url schema-url
                       :ruleset ruleset-name
                       :timestamp (.toString (Instant/now))
                       :rules rules
                       :total_rules (count rules)}))

      (catch clojure.lang.ExceptionInfo e
        (let [data (ex-data e)]
          (log/error e "Discover rules request failed" data)
          (case (:type data)
            :pod-communication-error
            (error-response 503
                           "Failed to communicate with validation runner"
                           :pod-communication-error
                           data)

            (error-response 500
                           (.getMessage e)
                           :internal-error
                           data))))

      (catch Exception e
        (log/error e "Unexpected error in discover-rules handler")
        (error-response 500
                       "Internal server error"
                       :internal-error
                       {:message (.getMessage e)})))))

(defn discover-rulesets-handler
  "Handle GET /api/v1/discover-rulesets requests.

  Returns metadata and statistics for all available rulesets.
  No parameters required."
  [request]
  (log/info "Received discover-rulesets request")
  (try
    (let [rulesets (client/discover-rulesets)]
      (json-response 200
                    {:rulesets rulesets
                     :timestamp (.toString (java.time.Instant/now))
                     :total_rulesets (count rulesets)}))
    (catch clojure.lang.ExceptionInfo e
      (let [data (ex-data e)]
        (log/error e "Discover rulesets request failed" data)
        (case (:type data)
          :pod-communication-error
          (error-response 503
                         "Failed to communicate with validation runner"
                         :pod-communication-error
                         data)

          (error-response 500
                         (.getMessage e)
                         :internal-error
                         data))))
    (catch Exception e
      (log/error e "Unexpected error in discover-rulesets handler")
      (error-response 500
                     "Internal server error"
                     :internal-error
                     {:message (.getMessage e)}))))

(defn batch-handler
  "Handle POST /api/v1/batch requests.

  Request body:
  {
    \"entities\": [{\"entity_type\": \"loan\", \"entity_data\": {...}}, ...],
    \"id_fields\": {\"<schema_url>\": \"<id_field>\", ...},
    \"ruleset_name\": \"quick\",  (optional, default \"quick\")
    \"output_mode\": \"response\",  (optional, default \"response\", can be \"file\")
    \"output_path\": \"/results/output.json\"  (required if output_mode=\"file\")
  }

  Returns batch validation results or file write confirmation."
  [{:keys [body] :as request}]
  (let [entities (get body "entities")
        id-fields (get body "id_fields")
        ruleset-name (get body "ruleset_name" "quick")
        output-mode (get body "output_mode" "response")
        output-path (get body "output_path")
        ;; Convert id-fields map to list for Python API
        id-fields-list (if (map? id-fields)
                        (vec (vals id-fields))
                        id-fields)]

    ;; Validate required parameters
    (when-not entities
      (throw (ex-info "Missing required parameter: entities"
                     {:type :validation-error})))

    (when-not (vector? entities)
      (throw (ex-info "Parameter 'entities' must be an array"
                     {:type :validation-error})))

    (when-not id-fields
      (throw (ex-info "Missing required parameter: id_fields"
                     {:type :validation-error})))

    (when (and (= output-mode "file") (not output-path))
      (throw (ex-info "Parameter 'output_path' required when output_mode='file'"
                     {:type :validation-error})))

    (log/info "Received batch validation request"
              {:entity-count (count entities)
               :ruleset ruleset-name
               :output-mode output-mode
               :id-fields-count (count id-fields)})

    (try
      (let [results (client/batch-validate entities
                                           id-fields-list
                                           ruleset-name)

            ;; Calculate overall statistics
            total-entities (count results)
            completed (count (filter #(= "completed" (get % "status")) results))
            errors (count (filter #(= "error" (get % "status")) results))
            entities-with-failures
              (count (filter (fn [r]
                              (and (= "completed" (get r "status"))
                                   (> (get-in r ["summary" "failed"]) 0)))
                            results))

            batch-id (str "BATCH-" (.format (DateTimeFormatter/ofPattern "yyyy-MM-dd-HHmmss")
                                           (LocalDateTime/now)))

            response-data
            {"batch_id" batch-id
             "timestamp" (.toString (Instant/now))
             "mode" "batch"
             "entity_count" total-entities
             "results" results
             "overall_summary" {"total_entities" total-entities
                               "completed" completed
                               "errors" errors
                               "entities_with_failures" entities-with-failures}}]

        ;; Handle output mode
        (case output-mode
          "response"
          (json-response 200 response-data)

          "file"
          (do
            (file-io/write-json-file output-path response-data)
            (json-response 200
                          {"batch_id" batch-id
                           "status" "completed"
                           "output_path" output-path
                           "entity_count" total-entities
                           "message" "Results written to file"}))

          ;; Invalid output mode
          (throw (ex-info "Invalid output_mode. Must be 'response' or 'file'"
                         {:type :validation-error
                          :output-mode output-mode}))))

      (catch clojure.lang.ExceptionInfo e
        (let [data (ex-data e)]
          (log/error e "Batch validation request failed" data)
          (case (:type data)
            :validation-error
            (error-response 400 (.getMessage e) :validation-error data)

            :file-fetch-error
            (error-response 500 "Failed to fetch input file" :file-fetch-error data)

            :file-write-error
            (error-response 500 "Failed to write output file" :file-write-error data)

            :pod-communication-error
            (error-response 503 "Failed to communicate with validation runner"
                          :pod-communication-error data)

            (error-response 500 (.getMessage e) :internal-error data))))

      (catch Exception e
        (log/error e "Unexpected error in batch handler")
        (error-response 500 "Internal server error" :internal-error
                       {:message (.getMessage e)})))))

(defn batch-file-handler
  "Handle POST /api/v1/batch-file requests.

  Request body:
  {
    \"file_uri\": \"file:///data/loans.json\",
    \"entity_types\": {\"<schema_url>\": \"loan\", ...},
    \"id_fields\": {\"<schema_url>\": \"loan_number\", ...},
    \"ruleset_name\": \"thorough\",  (optional, default \"quick\")
    \"output_mode\": \"file\",  (optional, default \"response\")
    \"output_path\": \"/results/validation_results.json\"  (required if output_mode=\"file\")
  }

  Returns batch validation results or file write confirmation."
  [{:keys [body] :as request}]
  (let [file-uri (get body "file_uri")
        entity-types (get body "entity_types")
        id-fields (get body "id_fields")
        ruleset-name (get body "ruleset_name" "quick")
        output-mode (get body "output_mode" "response")
        output-path (get body "output_path")]

    ;; Validate required parameters
    (when-not file-uri
      (throw (ex-info "Missing required parameter: file_uri"
                     {:type :validation-error})))

    (when-not entity-types
      (throw (ex-info "Missing required parameter: entity_types"
                     {:type :validation-error})))

    (when-not (map? entity-types)
      (throw (ex-info "Parameter 'entity_types' must be a map"
                     {:type :validation-error})))

    (when-not id-fields
      (throw (ex-info "Missing required parameter: id_fields"
                     {:type :validation-error})))

    (when-not (map? id-fields)
      (throw (ex-info "Parameter 'id_fields' must be a map"
                     {:type :validation-error})))

    (when (and (= output-mode "file") (not output-path))
      (throw (ex-info "Parameter 'output_path' required when output_mode='file'"
                     {:type :validation-error})))

    (log/info "Received batch-file validation request"
              {:file-uri file-uri
               :entity-types-count (count entity-types)
               :id-fields-count (count id-fields)
               :ruleset ruleset-name
               :output-mode output-mode})

    (try
      (let [results (client/batch-file-validate file-uri
                                                entity-types
                                                id-fields
                                                ruleset-name)

            ;; Calculate overall statistics
            total-entities (count results)
            completed (count (filter #(= "completed" (get % "status")) results))
            errors (count (filter #(= "error" (get % "status")) results))
            entities-with-failures
              (count (filter (fn [r]
                              (and (= "completed" (get r "status"))
                                   (> (get-in r ["summary" "failed"]) 0)))
                            results))

            batch-id (str "BATCH-" (.format (DateTimeFormatter/ofPattern "yyyy-MM-dd-HHmmss")
                                           (LocalDateTime/now)))

            response-data
            {"batch_id" batch-id
             "timestamp" (.toString (Instant/now))
             "mode" "batch-file"
             "file_uri" file-uri
             "entity_types" entity-types
             "id_fields" id-fields
             "entity_count" total-entities
             "results" results
             "overall_summary" {"total_entities" total-entities
                               "completed" completed
                               "errors" errors
                               "entities_with_failures" entities-with-failures}}]

        ;; Handle output mode
        (case output-mode
          "response"
          (json-response 200 response-data)

          "file"
          (do
            (file-io/write-json-file output-path response-data)
            (json-response 200
                          {"batch_id" batch-id
                           "status" "completed"
                           "file_uri" file-uri
                           "output_path" output-path
                           "entity_count" total-entities
                           "message" "Results written to file"}))

          ;; Invalid output mode
          (throw (ex-info "Invalid output_mode. Must be 'response' or 'file'"
                         {:type :validation-error
                          :output-mode output-mode}))))

      (catch clojure.lang.ExceptionInfo e
        (let [data (ex-data e)]
          (log/error e "Batch-file validation request failed" data)
          (case (:type data)
            :validation-error
            (error-response 400 (.getMessage e) :validation-error data)

            :file-fetch-error
            (error-response 500 "Failed to fetch input file" :file-fetch-error data)

            :json-parse-error
            (error-response 500 "Failed to parse JSON file" :json-parse-error data)

            :file-write-error
            (error-response 500 "Failed to write output file" :file-write-error data)

            :pod-communication-error
            (error-response 503 "Failed to communicate with validation runner"
                          :pod-communication-error data)

            (error-response 500 (.getMessage e) :internal-error data))))

      (catch Exception e
        (log/error e "Unexpected error in batch-file handler")
        (error-response 500 "Internal server error" :internal-error
                       {:message (.getMessage e)})))))

(defn health-handler
  "Handle GET /health requests.

  Simple health check endpoint."
  [request]
  (json-response 200
                {:status "healthy"
                 :timestamp (.toString (Instant/now))}))
