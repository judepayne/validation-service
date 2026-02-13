(ns validation-service.core
  (:require [validation-service.config :as config]
            [validation-service.api.routes :as routes]
            [ring.adapter.jetty :as jetty]
            [clojure.tools.logging :as log])
  (:gen-class))

(defn create-server
  "Create Jetty server instance.

  Args:
    web-config - Web configuration map with :service key
    library-config - Library configuration map

  Returns:
    Jetty server instance"
  [web-config library-config]
  (let [port (get-in web-config [:service :port] 8080)
        host (get-in web-config [:service :host] "0.0.0.0")
        handler (routes/create-handler library-config)]

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
    ;; Load separate configurations
    (let [library-config (config/load-library-config)
          web-config (config/load-web-config)]
      (log/info "Configuration loaded successfully")

      (let [server (create-server web-config library-config)]
        (log/info "Validation service started successfully")
        (log/info "Ready to accept requests")

        ;; Register shutdown hook
        (.addShutdownHook (Runtime/getRuntime)
                         (Thread. (fn []
                                   (log/info "Shutting down validation service")
                                   (.stop server)
                                   (log/info "Validation service stopped"))))

        ;; Block main thread
        (.join server)))

    (catch Exception e
      (log/error e "Failed to start server")
      (System/exit 1))))
