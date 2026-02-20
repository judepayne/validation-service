(ns validation-service.core
  (:require [validation-service.config :as config]
            [validation-service.api.routes :as routes]
            [validation-service.client.lifecycle :as client]
            [ring.adapter.jetty :as jetty]
            [clojure.tools.logging :as log])
  (:gen-class))

(defn create-server
  "Create Jetty server instance.

  Args:
    web-config - Web configuration map with :service key

  Returns:
    Jetty server instance"
  [web-config]
  (let [port (get-in web-config [:service :port] 8080)
        host (get-in web-config [:service :host] "0.0.0.0")
        handler (routes/create-handler)]

    (log/info "Starting server" {:port port :host host})
    (jetty/run-jetty handler
                     {:port port
                      :host host
                      :join? false})))

(defn -main
  "Application entry point."
  [& args]
  (log/info "===== Starting Validation Service =====")
  (try
    ;; Load web configuration
    (let [web-config (config/load-web-config)]
      (log/info "Configuration loaded successfully")

      ;; Start validation-lib-py client
      (client/start-client! (:validation_lib_py web-config))
      (log/info "validation-lib-py client initialized")

      (let [server (create-server web-config)]
        (log/info "Validation service started successfully")
        (log/info "Ready to accept requests")

        ;; Register shutdown hook
        (.addShutdownHook (Runtime/getRuntime)
                         (Thread. (fn []
                                   (log/info "Shutting down validation service")
                                   (client/stop-client!)
                                   (.stop server)
                                   (log/info "Validation service stopped"))))

        ;; Block main thread
        (.join server)))

    (catch Exception e
      (log/error e "Failed to start server")
      (System/exit 1))))
