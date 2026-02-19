(ns validation-service.config
  "Configuration loading utilities for validation service."
  (:require [aero.core :as aero]
            [clojure.java.io :as io]))

(defn load-web-config
  "Load web service configuration from resources/web-config.edn.

  Returns:
    Map with :service, :cors, :logging, :monitoring config"
  []
  (aero/read-config (io/resource "web-config.edn")))
