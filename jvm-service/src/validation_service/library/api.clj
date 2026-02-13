(ns validation-service.library.api
  "Public API for validation service library.

  This protocol defines the core validation operations independent of HTTP transport.
  Implementations should return raw data structures (maps/vectors), not Ring responses."
  (:require [validation-service.orchestration.workflow :as workflow]
            [validation-service.runner.pods-client :as pods-client]
            [clojure.tools.logging :as log]))

(defprotocol ValidationService
  "Core validation service operations."

  (validate [this entity-type entity-data ruleset-name]
    "Execute validation rules for a single entity.

    Args:
      entity-type - String entity type (loan, facility, deal)
      entity-data - Map with entity data (must include $schema)
      ruleset-name - String ruleset name (quick, thorough, etc.)

    Returns:
      Vector of validation result maps:
      [{\"rule_id\" \"rule_001_v1\"
        \"status\" \"PASS\"|\"FAIL\"|\"NORUN\"
        \"message\" \"...\"
        \"execution_time_ms\" 123
        ...}]")

  (discover-rules [this entity-type schema-url ruleset-name]
    "Discover applicable rules for an entity type and schema.

    Args:
      entity-type - String entity type
      schema-url - String schema URL (file://, http://, https://)
      ruleset-name - String ruleset name

    Returns:
      Vector of rule metadata maps:
      [{\"rule_id\" \"rule_001_v1\"
        \"description\" \"...\"
        \"validates\" \"loan\"
        \"required_data\" [...]
        \"field_dependencies\" [...]
        \"applicable_schemas\" [...]
        ...}]")

  (batch-validate [this entities id-fields ruleset-name]
    "Execute validation for multiple entities with inline data.

    Args:
      entities - Vector of entity maps [{\"entity_type\" \"loan\" \"entity_data\" {...}}]
      id-fields - Map of schema-url to id-field {\"<schema>\" \"loan_number\"}
      ruleset-name - String ruleset name

    Returns:
      Vector of per-entity result maps:
      [{\"entity_type\" \"loan\"
        \"entity_id\" \"LN-001\"
        \"status\" \"completed\"|\"error\"
        \"results\" [...]
        \"summary\" {...}}]")

  (batch-file-validate [this file-uri entity-types id-fields ruleset-name]
    "Execute validation for entities loaded from file URI.

    Args:
      file-uri - String URI (file://, http://, https://)
      entity-types - Map of schema-url to entity-type {\"<schema>\" \"loan\"}
      id-fields - Map of schema-url to id-field {\"<schema>\" \"loan_number\"}
      ruleset-name - String ruleset name

    Returns:
      Vector of per-entity result maps (same format as batch-validate)"))

(defrecord ValidationServiceImpl [runner-client config]
  ValidationService

  (validate [this entity-type entity-data ruleset-name]
    (workflow/execute-validation runner-client
                                config
                                entity-type
                                entity-data
                                ruleset-name))

  (discover-rules [this entity-type schema-url ruleset-name]
    (workflow/execute-discover-rules runner-client
                                    config
                                    entity-type
                                    schema-url
                                    ruleset-name))

  (batch-validate [this entities id-fields ruleset-name]
    (workflow/execute-batch-validation runner-client
                                      config
                                      entities
                                      id-fields
                                      ruleset-name))

  (batch-file-validate [this file-uri entity-types id-fields ruleset-name]
    (workflow/execute-batch-file-validation runner-client
                                           config
                                           file-uri
                                           entity-types
                                           id-fields
                                           ruleset-name)))

(defn create-service
  "Create ValidationService instance from library configuration.

  Initializes Python runner pod and returns service implementation.

  Args:
    config - Library configuration map with :python_runner and :coordination_service

  Returns:
    ValidationService implementation (ValidationServiceImpl record)

  Throws:
    ExceptionInfo if pod initialization fails"
  [config]
  (log/info "Initializing validation service library")
  (let [runner-client (pods-client/create-pods-client config)]
    (log/info "Validation service library initialized")
    (->ValidationServiceImpl runner-client config)))

