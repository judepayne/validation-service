(ns validation-service.config
  (:require [aero.core :as aero]
            [clojure.java.io :as io]))

(defn load-library-config
  "Load library configuration from library-config.edn.

  Returns:
    Map with :python_runner and :coordination_service keys"
  []
  (aero/read-config (io/resource "library-config.edn")))

(defn load-web-config
  "Load web configuration from web-config.edn.

  Returns:
    Map with :service, :cors, :logging, :monitoring keys"
  []
  (aero/read-config (io/resource "web-config.edn")))

(defn load-config
  "Load configuration from config.edn file (DEPRECATED).

  Use load-library-config or load-web-config for new code.

  Config path priority:
  1. System property: -Dconfig.path=/path/to/config.edn
  2. Default: config.edn in current directory"
  []
  (let [config-path (or (System/getProperty "config.path")
                        "config.edn")
        config-file (io/file config-path)]
    (when-not (.exists config-file)
      (throw (ex-info (str "Configuration file not found: " config-path)
                      {:config-path config-path})))
    (aero/read-config config-file)))
