(ns validation-service.orchestration.workflow
  (:require [validation-service.runner.protocol :as runner]
            [validation-service.orchestration.coordination :as coord]
            [validation-service.utils.file-io :as file-io]
            [clojure.tools.logging :as log]))

(defn execute-validation
  "Execute full validation workflow.

  Workflow steps:
  1. Call runner get-required-data to discover what external data is needed
  2. Fetch required data from coordination service (stub returns nil)
  3. Call runner validate with entity data + required data
  4. Return validation results

  Args:
    runner-client - ValidationRunnerClient instance
    config - Service configuration
    entity-type - Type of entity ('loan', 'facility', 'deal')
    entity-data - Entity data map to validate
    ruleset-name - Rule set to use ('quick', 'thorough', etc.)

  Returns:
    Vector of validation results (hierarchical structure)"
  [runner-client config entity-type entity-data ruleset-name]
  (log/info "Starting validation workflow"
            {:entity-type entity-type
             :ruleset ruleset-name
             :entity-id (get entity-data "id")})

  ;; Step 1: Get schema URL from entity data and normalize it
  (let [schema-url-raw (get entity-data "$schema")
        schema-url (file-io/normalize-file-uri schema-url-raw)
        _ (when (not= schema-url schema-url-raw)
            (log/debug "Normalized schema URL" {:from schema-url-raw :to schema-url}))

        ;; Update entity data with normalized schema URL for Python runner
        entity-data-normalized (if (not= schema-url schema-url-raw)
                                (assoc entity-data "$schema" schema-url)
                                entity-data)

        ;; Step 2: Discover required data vocabulary terms
        vocabulary-terms (runner/get-required-data runner-client
                                                   entity-type
                                                   schema-url
                                                   ruleset-name)
        _ (log/debug "Required data terms:" vocabulary-terms)

        ;; Step 3: Fetch required data from coordination service
        required-data (coord/fetch-required-data config
                                                 entity-type
                                                 vocabulary-terms)
        _ (log/debug "Required data fetched (stub):" required-data)

        ;; Step 4: Execute validation
        results (runner/validate runner-client
                                entity-type
                                entity-data-normalized
                                ruleset-name
                                required-data)]

    (log/info "Validation workflow completed"
              {:entity-type entity-type
               :total-rules (count results)
               :passed (count (filter #(= "PASS" (get % "status")) results))
               :failed (count (filter #(= "FAIL" (get % "status")) results))})

    results))

(defn execute-discover-rules
  "Execute rule discovery workflow.

  Args:
    runner-client - ValidationRunnerClient instance
    config - Service configuration
    entity-type - Type of entity
    schema-url - Schema URL for version routing
    ruleset-name - Rule set to use

  Returns:
    Map of rule-id to metadata"
  [runner-client config entity-type schema-url ruleset-name]
  (log/info "Starting rule discovery workflow"
            {:entity-type entity-type
             :schema-url schema-url
             :ruleset ruleset-name})

  ;; Construct minimal entity-data with just schema for Python runner
  (let [entity-data {"$schema" schema-url}
        rules (runner/discover-rules runner-client
                                     entity-type
                                     entity-data
                                     ruleset-name)]
    (log/info "Rule discovery completed"
              {:entity-type entity-type
               :total-rules (count rules)})
    rules))

(defn- validate-schemas-against-id-fields
  "Validate that all schemas in batch have corresponding id_fields entries.

  Args:
    schemas-in-batch - Set of schema URLs found in batch
    id-fields - Map of schema URL to id field name

  Throws:
    ExceptionInfo if validation fails"
  [schemas-in-batch id-fields]
  (let [id-fields-keys (set (keys id-fields))
        missing-schemas (clojure.set/difference schemas-in-batch id-fields-keys)]
    (when (seq missing-schemas)
      (throw (ex-info "Missing id_fields entries for schemas found in batch"
                     {:type :validation-error
                      :missing-schemas (vec missing-schemas)
                      :schemas-in-batch (vec schemas-in-batch)
                      :id-fields-keys (vec id-fields-keys)})))))

(defn execute-batch-validation
  "Execute validation workflow for multiple entities.

  Workflow:
  1. Extract all schemas from batch and validate against id_fields
  2. For each entity in batch
  3. Extract entity_type, entity_data, and ID using schema-specific id_field
  4. Call execute-validation (reuses existing workflow)
  5. Aggregate results

  Args:
    runner-client - ValidationRunnerClient instance
    config - Service configuration
    entities - Vector of entity maps: [{\"entity_type\" \"loan\", \"entity_data\" {...}}, ...]
    id-fields - Map of schema URL to id field name: {\"<schema_url>\" \"<id_field>\", ...}
    ruleset-name - Rule set to use

  Returns:
    Vector of per-entity results with correlation metadata"
  [runner-client config entities id-fields ruleset-name]
  (log/info "Starting batch validation workflow"
            {:entity-count (count entities)
             :ruleset ruleset-name})

  ;; Pre-process: Extract all schemas and validate against id_fields
  (let [schemas-in-batch (->> entities
                              (map #(get-in % ["entity_data" "$schema"]))
                              (remove nil?)
                              set)]
    (validate-schemas-against-id-fields schemas-in-batch id-fields))

  (let [start-time (System/currentTimeMillis)
        results
        (mapv (fn [entity]
                (let [entity-type (get entity "entity_type")
                      entity-data (get entity "entity_data")
                      schema (get entity-data "$schema")
                      id-field (get id-fields schema)
                      entity-id (if id-field
                                  (get entity-data id-field "UNKNOWN")
                                  "UNKNOWN")]
                  (try
                    (let [validation-results
                          (execute-validation runner-client config
                                            entity-type entity-data
                                            ruleset-name)

                          total (count validation-results)
                          passed (count (filter #(= "PASS" (get % "status")) validation-results))
                          failed (count (filter #(= "FAIL" (get % "status")) validation-results))
                          norun (count (filter #(= "NORUN" (get % "status")) validation-results))]

                      {"entity_type" entity-type
                       "entity_id" entity-id
                       "schema" schema
                       "status" "completed"
                       "results" validation-results
                       "summary" {"total_rules" total
                                 "passed" passed
                                 "failed" failed
                                 "not_run" norun}})

                    (catch Exception e
                      (log/error e "Entity validation failed"
                                {:entity-type entity-type
                                 :entity-id entity-id
                                 :schema schema})
                      {"entity_type" entity-type
                       "entity_id" entity-id
                       "schema" schema
                       "status" "error"
                       "error" (.getMessage e)}))))
              entities)

        end-time (System/currentTimeMillis)
        total-time (- end-time start-time)]

    (log/info "Batch validation completed"
              {:entity-count (count entities)
               :total-time-ms total-time})

    results))

(defn execute-batch-file-validation
  "Execute validation workflow for entities from file.

  Workflow:
  1. Fetch file from URI (file://, http://, https://)
  2. Parse JSON array
  3. Extract all schemas from entities and validate against entity_types and id_fields
  4. For each entity data object:
     a. Determine entity_type from schema using entity_types map
     b. Extract ID using schema-specific id_field from id_fields map
     c. Call execute-validation
     d. Include ID in result

  Args:
    runner-client - ValidationRunnerClient instance
    config - Service configuration
    file-uri - URI to input file
    entity-types - Map of schema URL to entity type: {\"<schema_url>\" \"loan\", ...}
    id-fields - Map of schema URL to id field name: {\"<schema_url>\" \"loan_number\", ...}
    ruleset-name - Rule set to use

  Returns:
    Vector of per-entity results with ID correlation"
  [runner-client config file-uri entity-types id-fields ruleset-name]
  (log/info "Starting batch file validation workflow"
            {:file-uri file-uri
             :entity-types entity-types
             :id-fields id-fields
             :ruleset ruleset-name})

  (let [;; Fetch and parse file
        file-content (file-io/fetch-file-from-uri file-uri)
        entities-data (file-io/parse-json-array file-content)

        ;; Pre-process: Extract all schemas and validate
        schemas-in-batch (->> entities-data
                              (map #(get % "$schema"))
                              (remove nil?)
                              set)]

    (validate-schemas-against-id-fields schemas-in-batch id-fields)

    ;; Validate entity_types has all required schemas
    (let [entity-types-keys (set (keys entity-types))
          missing-entity-types (clojure.set/difference schemas-in-batch entity-types-keys)]
      (when (seq missing-entity-types)
        (throw (ex-info "Missing entity_types entries for schemas found in batch"
                       {:type :validation-error
                        :missing-schemas (vec missing-entity-types)
                        :schemas-in-batch (vec schemas-in-batch)
                        :entity-types-keys (vec entity-types-keys)}))))

    (let [start-time (System/currentTimeMillis)

          results
          (mapv (fn [entity-data]
                  (let [schema (get entity-data "$schema")
                        entity-type (get entity-types schema)
                        id-field (get id-fields schema)
                        entity-id (if id-field
                                    (get entity-data id-field "UNKNOWN")
                                    "UNKNOWN")]

                    (try
                      (let [validation-results
                            (execute-validation runner-client config
                                              entity-type
                                              entity-data
                                              ruleset-name)

                          total (count validation-results)
                          passed (count (filter #(= "PASS" (get % "status")) validation-results))
                          failed (count (filter #(= "FAIL" (get % "status")) validation-results))
                          norun (count (filter #(= "NORUN" (get % "status")) validation-results))]

                        {"entity_type" entity-type
                         "entity_id" entity-id
                         "schema" schema
                         "status" "completed"
                         "results" validation-results
                         "summary" {"total_rules" total
                                   "passed" passed
                                   "failed" failed
                                   "not_run" norun}})

                      (catch Exception e
                        (log/error e "Entity validation failed"
                                  {:entity-type entity-type
                                   :entity-id entity-id
                                   :schema schema})
                        {"entity_type" entity-type
                         "entity_id" entity-id
                         "schema" schema
                         "status" "error"
                         "error" (.getMessage e)}))))
                entities-data)

          end-time (System/currentTimeMillis)
          total-time (- end-time start-time)]

      (log/info "Batch file validation completed"
                {:entity-count (count entities-data)
                 :total-time-ms total-time})

      results)))
