(ns validation-service.config
  (:require [aero.core :as aero]
            [clojure.java.io :as io]))

(defn load-config
  "Load configuration from config.edn file.

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
