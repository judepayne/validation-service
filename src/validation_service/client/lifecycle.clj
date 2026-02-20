(ns validation-service.client.lifecycle
  "Manages validation-lib-py client lifecycle.

  Provides global client instance and wrapper functions for easy access."
  (:require [validation-service.client.jsonrpc-client :as rpc]
            [clojure.tools.logging :as log]))

(defonce ^{:private true :doc "Global client state atom."} client-state
  (atom nil))

(declare stop-client!)

(defn start-client!
  "Start validation-lib-py client and store in global state.

  Args:
    config - Configuration map (see jsonrpc-client/start-server)

  Returns:
    Client instance"
  [config]
  (when @client-state
    (log/warn "Client already started, stopping existing client first")
    (stop-client!))

  (log/info "Starting validation-lib-py client")
  (let [client (rpc/start-server config)]
    (reset! client-state client)
    (log/info "Client started and stored in global state")
    client))

(defn stop-client!
  "Stop validation-lib-py client and clear global state."
  []
  (when-let [client @client-state]
    (log/info "Stopping validation-lib-py client")
    (rpc/stop-server client)
    (reset! client-state nil)
    (log/info "Client stopped and state cleared"))
  nil)

(defn get-client
  "Get current client instance.

  Throws:
    ExceptionInfo if client not started"
  []
  (or @client-state
      (throw (ex-info "Client not started"
                      {:type :client-not-started
                       :message "Call start-client! before using validation functions"}))))

(defn client-started?
  "Check if client is currently running."
  []
  (some? @client-state))

;; Wrapper functions that use global client

(defn validate
  "Validate a single entity using global client.

  See jsonrpc-client/validate for full documentation."
  [entity-type entity-data ruleset-name]
  (rpc/validate (get-client) entity-type entity-data ruleset-name))

(defn discover-rules
  "Discover available rules using global client.

  See jsonrpc-client/discover-rules for full documentation."
  [entity-type entity-data ruleset-name]
  (rpc/discover-rules (get-client) entity-type entity-data ruleset-name))

(defn discover-rulesets
  "Discover all rulesets using global client.

  See jsonrpc-client/discover-rulesets for full documentation."
  []
  (rpc/discover-rulesets (get-client)))

(defn batch-validate
  "Batch validate entities using global client.

  See jsonrpc-client/batch-validate for full documentation."
  [entities id-fields ruleset-name]
  (rpc/batch-validate (get-client) entities id-fields ruleset-name))

(defn batch-file-validate
  "Batch validate from file using global client.

  See jsonrpc-client/batch-file-validate for full documentation."
  [file-uri entity-types id-fields ruleset-name]
  (rpc/batch-file-validate (get-client) file-uri entity-types id-fields ruleset-name))

(defn reload-logic
  "Reload business logic using global client.

  See jsonrpc-client/reload-logic for full documentation."
  []
  (rpc/reload-logic (get-client)))

(defn get-cache-age
  "Get cache age using global client.

  See jsonrpc-client/get-cache-age for full documentation."
  []
  (rpc/get-cache-age (get-client)))
