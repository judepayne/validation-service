(ns validation-service.runner.protocol)

(defprotocol ValidationRunnerClient
  "Protocol for communicating with validation runner (transport-agnostic)."

  (get-required-data [this entity-type schema-url ruleset-name]
    "Get list of required data vocabulary terms.

    Returns: Vector of strings")

  (validate [this entity-type entity-data ruleset-name required-data]
    "Execute validation rules.

    Returns: Vector of result maps with hierarchical structure")

  (discover-rules [this entity-type entity-data ruleset-name]
    "Discover all rules and their metadata.

    Returns: Map of rule-id to metadata"))
