(ns validation-service.client.jsonrpc-client
  "JSON-RPC client for validation-lib-py.

  Manages subprocess lifecycle and JSON-RPC communication over stdin/stdout."
  (:require [clojure.java.io :as io]
            [cheshire.core :as json]
            [clojure.tools.logging :as log])
  (:import [java.io BufferedReader BufferedWriter InputStreamReader OutputStreamWriter]))

(defn- read-response
  "Read and parse JSON-RPC response from subprocess."
  [^BufferedReader reader]
  (when-let [line (.readLine reader)]
    (try
      (json/parse-string line true)
      (catch Exception e
        (log/error e "Failed to parse JSON-RPC response" {:line line})
        (throw (ex-info "Invalid JSON-RPC response"
                        {:type :parse-error
                         :line line}
                        e))))))

(defn- send-request
  "Send JSON-RPC request to subprocess."
  [^BufferedWriter writer request]
  (try
    (.write writer (json/generate-string request))
    (.newLine writer)
    (.flush writer)
    (catch Exception e
      (log/error e "Failed to send JSON-RPC request" {:request request})
      (throw (ex-info "Failed to send request"
                      {:type :write-error
                       :request request}
                      e)))))

(defn start-server
  "Start validation-lib JSON-RPC server subprocess.

  Args:
    config - Configuration map with:
             :python-executable - Path to python (default: python3)
             :script-path - Path to validation-lib directory (required)
             :debug - Enable debug logging (default: false)

  Returns:
    Map with :process, :reader, :writer, :request-counter"
  [{:keys [python-executable script-path debug]
    :or {python-executable "python3"
         debug false}}]
  (log/info "Starting validation-lib JSON-RPC server"
            {:python python-executable
             :script-path script-path
             :debug debug})

  (let [cmd (cond-> [python-executable "-m" "validation_lib.jsonrpc_server"]
              debug (conj "--debug"))

        ; Start subprocess
        pb (ProcessBuilder. ^java.util.List cmd)
        script-file (io/file script-path)
        _ (.directory pb script-file)

        process (.start pb)

        ; Get I/O streams
        reader (BufferedReader. (InputStreamReader. (.getInputStream process) "UTF-8"))
        writer (BufferedWriter. (OutputStreamWriter. (.getOutputStream process) "UTF-8"))]

    (log/info "validation-lib JSON-RPC server started successfully")

    {:process process
     :reader reader
     :writer writer
     :request-counter (atom 0)}))

(defn stop-server
  "Stop validation-lib-py JSON-RPC server subprocess."
  [{:keys [^java.lang.Process process ^BufferedReader reader ^BufferedWriter writer]}]
  (log/info "Stopping validation-lib-py JSON-RPC server")
  (try
    (.close writer)
    (.close reader)
    (.destroy process)
    (log/info "validation-lib-py server stopped successfully")
    (catch Exception e
      (log/error e "Error stopping validation-lib-py server")
      (.destroyForcibly process))))

(defn call-rpc
  "Call JSON-RPC method on validation-lib-py server.

  Args:
    client - Client map from start-server
    method - JSON-RPC method name (string)
    params - Method parameters (map)

  Returns:
    Result from JSON-RPC response, or throws on error"
  [{:keys [reader writer request-counter]} method params]
  (let [request-id (swap! request-counter inc)
        request {:jsonrpc "2.0"
                 :id request-id
                 :method method
                 :params params}]

    (log/debug "Sending JSON-RPC request" {:method method :id request-id})

    ; Send request
    (send-request writer request)

    ; Read response
    (let [response (read-response reader)]
      (log/debug "Received JSON-RPC response" {:method method :id request-id})

      (cond
        ; Success
        (contains? response :result)
        (:result response)

        ; Error
        (contains? response :error)
        (let [error (:error response)]
          (log/error "JSON-RPC error" {:method method :error error})
          (throw (ex-info "JSON-RPC error"
                          {:type :jsonrpc-error
                           :error error
                           :method method
                           :params params})))

        ; Invalid response
        :else
        (throw (ex-info "Invalid JSON-RPC response"
                        {:type :invalid-response
                         :response response}))))))

;; High-level API wrappers

(defn validate
  "Validate a single entity.

  Args:
    client - JSON-RPC client
    entity-type - Type of entity (e.g., 'loan')
    entity-data - Entity data map
    ruleset-name - Ruleset to use (e.g., 'quick')

  Returns:
    List of validation results"
  [client entity-type entity-data ruleset-name]
  (call-rpc client "validate"
            {:entity_type entity-type
             :entity_data entity-data
             :ruleset_name ruleset-name}))

(defn discover-rules
  "Discover available rules for an entity type.

  Args:
    client - JSON-RPC client
    entity-type - Type of entity
    entity-data - Sample entity data
    ruleset-name - Ruleset to query

  Returns:
    Map of rule metadata"
  [client entity-type entity-data ruleset-name]
  (call-rpc client "discover_rules"
            {:entity_type entity-type
             :entity_data entity-data
             :ruleset_name ruleset-name}))

(defn discover-rulesets
  "Discover all available rulesets.

  Args:
    client - JSON-RPC client

  Returns:
    Map of ruleset metadata"
  [client]
  (call-rpc client "discover_rulesets" {}))

(defn batch-validate
  "Validate multiple entities.

  Args:
    client - JSON-RPC client
    entities - List of entity maps
    id-fields - List of field names for entity identification
    ruleset-name - Ruleset to use

  Returns:
    List of per-entity validation results"
  [client entities id-fields ruleset-name]
  (call-rpc client "batch_validate"
            {:entities entities
             :id_fields id-fields
             :ruleset_name ruleset-name}))

(defn batch-file-validate
  "Validate entities from a file.

  Args:
    client - JSON-RPC client
    file-uri - URI to file containing entities
    entity-types - List of entity types in file
    id-fields - List of field names for entity identification
    ruleset-name - Ruleset to use

  Returns:
    List of validation results"
  [client file-uri entity-types id-fields ruleset-name]
  (call-rpc client "batch_file_validate"
            {:file_uri file-uri
             :entity_types entity-types
             :id_fields id-fields
             :ruleset_name ruleset-name}))

(defn reload-logic
  "Reload business logic from source.

  Args:
    client - JSON-RPC client

  Returns:
    Status map"
  [client]
  (call-rpc client "reload_logic" {}))

(defn get-cache-age
  "Get cache age in seconds.

  Args:
    client - JSON-RPC client

  Returns:
    Cache age map"
  [client]
  (call-rpc client "get_cache_age" {}))
