(ns validation-service.api.routes
  (:require [validation-service.api.handlers :as handlers]
            [validation-service.api.schemas :as schemas]
            [validation-service.runner.pods-client :as pods-client]
            [reitit.ring :as ring]
            [reitit.swagger :as swagger]
            [reitit.swagger-ui :as swagger-ui]
            [ring.middleware.json :refer [wrap-json-response wrap-json-body]]
            [clojure.tools.logging :as log]))

(defn wrap-runner-client
  "Middleware to inject runner client and config into request.

  Adds :runner-client and :config to request map."
  [handler runner-client config]
  (fn [request]
    (handler (assoc request
                    :runner-client runner-client
                    :config config))))

(defn wrap-request-logging
  "Middleware to log incoming requests."
  [handler]
  (fn [request]
    (let [method (:request-method request)
          uri (:uri request)]
      (log/info "Incoming request" {:method method :uri uri})
      (let [response (handler request)]
        (log/info "Response" {:method method :uri uri :status (:status response)})
        response))))

(defn create-routes
  "Create Reitit route data structure with Swagger documentation.

  Returns data-driven route definition."
  []
  [["/swagger.json"
    {:get {:no-doc true
           :swagger {:info {:title "Validation Service API"
                           :description "RESTful API for entity validation using Python rules engine"
                           :version "1.0.0"}
                    :tags [{:name "validation" :description "Validation operations"}
                           {:name "discovery" :description "Rule discovery operations"}
                           {:name "system" :description "System health and status"}]}
           :handler (swagger/create-swagger-handler)}}]

   ["/api/v1"
    ["/validate"
     {:post {:handler handlers/validate-handler
             :summary "Validate entity data"
             :description "Execute validation rules against entity data and return hierarchical results"
             :tags ["validation"]
             :swagger {:produces ["application/json"]
                      :consumes ["application/json"]
                      :parameters [{:in "body"
                                   :name "body"
                                   :description "Validation request"
                                   :required true
                                   :schema {:example schemas/validate-request-example}}]}}}]

    ["/batch"
     {:post {:handler handlers/batch-handler
             :summary "Batch validate multiple entities"
             :description "Execute validation for multiple entities with inline data. Supports mixed entity types and flexible output (response or file)."
             :tags ["validation"]
             :swagger {:produces ["application/json"]
                      :consumes ["application/json"]
                      :parameters [{:in "body"
                                   :name "body"
                                   :description "Batch validation request with entities array"
                                   :required true
                                   :schema {:example schemas/batch-request-example}}]}}}]

    ["/batch-file"
     {:post {:handler handlers/batch-file-handler
             :summary "Batch validate entities from file"
             :description "Execute validation for entities loaded from a file URI (file://, http://, https://). All entities must be of the same type. Supports flexible output (response or file)."
             :tags ["validation"]
             :swagger {:produces ["application/json"]
                      :consumes ["application/json"]
                      :parameters [{:in "body"
                                   :name "body"
                                   :description "Batch file validation request with file URI and entity metadata"
                                   :required true
                                   :schema {:example schemas/batch-file-request-example}}]}}}]

    ["/discover-rules"
     {:post {:handler handlers/discover-rules-handler
             :summary "Discover validation rules"
             :description "Get comprehensive metadata about all applicable rules including dependencies and schemas. Accepts entity_type, schema_url, and ruleset_name."
             :tags ["discovery"]
             :swagger {:produces ["application/json"]
                      :consumes ["application/json"]
                      :parameters [{:in "body"
                                   :name "body"
                                   :description "Discovery request with entity_type, schema_url, and ruleset_name"
                                   :required true
                                   :schema {:example schemas/discover-rules-request-example}}]}}}]]

   ["/health"
    {:get {:handler handlers/health-handler
           :summary "Health check"
           :description "Check if the service is running and healthy"
           :tags ["system"]
           :responses {200 {:body ::schemas/health-response
                           :description "Service is healthy"}
                      503 {:description "Service unavailable"}}}}]])

(defn create-handler
  "Create Ring handler with routes, Swagger UI, and middleware.

  Args:
    config - Service configuration map

  Returns:
    Ring handler function"
  [config]
  (let [;; Initialize runner client once
        runner-client (pods-client/create-pods-client config)

        ;; Create router from route data
        router (ring/router (create-routes))

        ;; Create ring handler with Swagger UI and default handlers
        app (ring/ring-handler
             router
             (ring/routes
              (swagger-ui/create-swagger-ui-handler
               {:path "/swagger-ui"
                :url "/swagger.json"
                :config {:validatorUrl nil
                        :operationsSorter "alpha"}})
              (ring/create-default-handler
               {:not-found (constantly {:status 404
                                       :body {:error "Not found"}})
                :method-not-allowed (constantly {:status 405
                                                :body {:error "Method not allowed"}})})))]

    (log/info "Creating application handler with middleware")
    (log/info "Swagger UI available at /swagger-ui")

    ;; Apply middleware (bottom-up order)
    (-> app
        (wrap-runner-client runner-client config)  ;; Inject dependencies
        (wrap-json-response)                       ;; Serialize response :body to JSON
        (wrap-json-body {:keywords? false})        ;; Parse JSON body (keep string keys)
        (wrap-request-logging))))                  ;; Log requests
