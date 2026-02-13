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

