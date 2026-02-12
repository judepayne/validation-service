(ns validation-service.runner.pods-client
  (:require [validation-service.runner.protocol :as proto]
            [babashka.pods :as pods]
            [clojure.tools.logging :as log]))

(defrecord PodsRunnerClient [config pod-namespace]
  proto/ValidationRunnerClient

  (get-required-data [this entity-type schema-url ruleset-name]
    (log/debug "Calling pod get-required-data"
               {:entity-type entity-type :ruleset ruleset-name})
    (try
      (pods/invoke pod-namespace 'get-required-data
                   {:entity_type entity-type
                    :schema_url schema-url
                    :ruleset_name ruleset-name})
      (catch Exception e
        (log/error e "Pod invocation failed: get-required-data")
        (throw (ex-info "Failed to get required data from runner"
                        {:type :pod-communication-error
                         :function "get-required-data"
                         :entity-type entity-type}
                        e)))))

  (validate [this entity-type entity-data ruleset-name required-data]
    (log/debug "Calling pod validate"
               {:entity-type entity-type :ruleset ruleset-name})
    (try
      (pods/invoke pod-namespace 'validate
                   {:entity_type entity-type
                    :entity_data entity-data
                    :ruleset_name ruleset-name
                    :required_data required-data})
      (catch Exception e
        (log/error e "Pod invocation failed: validate")
        (throw (ex-info "Failed to validate with runner"
                        {:type :pod-communication-error
                         :function "validate"
                         :entity-type entity-type}
                        e)))))

  (discover-rules [this entity-type entity-data ruleset-name]
    (log/debug "Calling pod discover-rules"
               {:entity-type entity-type :ruleset ruleset-name})
    (try
      (pods/invoke pod-namespace 'discover-rules
                   {:entity_type entity-type
                    :entity_data entity-data
                    :ruleset_name ruleset-name})
      (catch Exception e
        (log/error e "Pod invocation failed: discover-rules")
        (throw (ex-info "Failed to discover rules from runner"
                        {:type :pod-communication-error
                         :function "discover-rules"
                         :entity-type entity-type}
                        e))))))

(defn create-pods-client
  "Create and initialize a pods-based runner client.

  Spawns the Python runner process and loads it as a babashka pod.

  Args:
    config - Service configuration containing :python_runner settings

  Returns:
    PodsRunnerClient instance"
  [config]
  (let [python-exe (get-in config [:python_runner :executable])
        script-path (get-in config [:python_runner :script_path])
        config-path (get-in config [:python_runner :config_path])
        pod-namespace "pod.validation-runner"]

    (log/info "Loading Python runner pod"
              {:executable python-exe
               :script script-path
               :config config-path})

    (try
      (pods/load-pod [python-exe script-path config-path])
      (log/info "Python runner pod loaded successfully")
      (->PodsRunnerClient config pod-namespace)
      (catch Exception e
        (log/error e "Failed to load Python runner pod")
        (throw (ex-info "Failed to initialize runner client"
                        {:type :pod-initialization-error
                         :executable python-exe
                         :script script-path}
                        e))))))
