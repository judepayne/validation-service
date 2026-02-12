(ns validation-service.orchestration.coordination
  (:require [clojure.tools.logging :as log]))

(defn fetch-required-data
  "Fetch required data from coordination service.

  STUB IMPLEMENTATION: Always returns nil and logs the call.

  Args:
    config - Service configuration map
    entity-type - Type of entity ('loan', 'facility', 'deal')
    vocabulary-terms - List of required data vocabulary terms

  Returns:
    nil (stub implementation)"
  [config entity-type vocabulary-terms]
  (log/info "STUB: Coordination service called"
            {:entity-type entity-type
             :vocabulary-terms vocabulary-terms
             :coordination-url (get-in config [:coordination_service :base_url])})
  nil)

(comment
  ;; Future real implementation will look like:
  ;; (defn fetch-required-data [config entity-type vocabulary-terms]
  ;;   (let [url (get-in config [:coordination_service :base_url])
  ;;         response (http/post (str url "/fetch-data")
  ;;                             {:body (json/encode {:entity_type entity-type
  ;;                                                  :terms vocabulary-terms})})]
  ;;     (:body response)))
  )
