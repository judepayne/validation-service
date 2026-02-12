(ns validation-service.core
  (:require [validation-service.config :as config]
            [validation-service.api.routes :as routes]
            [ring.adapter.jetty :as jetty]
            [clojure.tools.logging :as log])
  (:gen-class))

(defn create-server
  "Create Jetty server instance."
  [config]
  (let [handler (routes/create-handler config)
        port (get-in config [:service :port] 8080)
        host (get-in config [:service :host] "0.0.0.0")]
    (log/info "Creating server on" host ":" port)
    {:server (jetty/run-jetty handler
                              {:port port
                               :host host
                               :join? false})
     :config config}))

(defn -main
  "Application entry point."
  [& args]
  (log/info "===== Starting Validation Service =====")
  (try
    (let [config (config/load-config)]
      (log/info "Configuration loaded successfully")
      (let [{:keys [server]} (create-server config)]
        (log/info "Server started successfully")
        (log/info "Ready to accept requests")
        (.join server)))  ;; Block main thread
    (catch Exception e
      (log/error e "Failed to start server")
      (System/exit 1))))
