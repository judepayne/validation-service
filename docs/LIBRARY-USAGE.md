# Using Validation Service as a Library

The validation service core logic is available as a library for embedding in other applications.

## Dependencies

Add to `deps.edn`:

```clojure
{:deps {validation-service/library {:local/root "../validation-service/jvm-service"}}}
```

## Basic Usage

```clojure
(require '[validation-service.library.api :as vlib])

;; 1. Load library configuration
(def config
  {:python_runner {:executable "python3"
                  :script_path "../python-runner/runner.py"
                  :config_path "../python-runner/config.yaml"
                  :spawn_timeout_ms 5000
                  :validation_timeout_ms 30000
                  :pool_size 5
                  :pool_max_idle_ms 300000}
   :coordination_service {:base_url "http://localhost:8081"
                         :timeout_ms 5000
                         :retry_attempts 3
                         :retry_delay_ms 1000
                         :circuit_breaker_enabled true
                         :failure_threshold 5
                         :reset_timeout_ms 60000}})

;; 2. Create service instance
(def service (vlib/create-service config))

;; 3. Validate entities
(def results
  (.validate service
            "loan"
            {"$schema" "file:///path/to/loan.schema.v1.0.0.json"
             "loan_number" "LN-001"
             "facility_id" "FAC-100"
             "financial" {"principal_amount" 100000
                         "outstanding_balance" 75000
                         "currency" "USD"
                         "interest_rate" 0.05}
             "dates" {"origination_date" "2024-01-01"
                     "maturity_date" "2025-01-01"}
             "status" "active"}
            "quick"))

;; Results is vector of validation result maps
(println "Total rules:" (count results))
(println "Passed:" (count (filter #(= "PASS" (get % "status")) results)))

;; 4. Discover rules
(def rules
  (.discover-rules service
                  "loan"
                  "file:///path/to/loan.schema.v1.0.0.json"
                  "quick"))

;; 5. Batch validation
(def batch-results
  (.batch-validate service
                  [{"entity_type" "loan"
                    "entity_data" {...}}
                   {"entity_type" "loan"
                    "entity_data" {...}}]
                  {"file:///path/to/loan.schema.v1.0.0.json" "loan_number"}
                  "thorough"))

;; 6. Batch file validation
(def file-results
  (.batch-file-validate service
                       "file:///data/loans.json"
                       {"file:///path/to/loan.schema.v1.0.0.json" "loan"}
                       {"file:///path/to/loan.schema.v1.0.0.json" "loan_number"}
                       "quick"))

;; 7. Cleanup (optional - currently a no-op)
(vlib/shutdown-service service)
```

## Protocol Methods

### validate

Execute validation rules for a single entity.

**Arguments:**
- `entity-type` - String entity type (loan, facility, deal)
- `entity-data` - Map with entity data (must include $schema)
- `ruleset-name` - String ruleset name (quick, thorough, etc.)

**Returns:**
Vector of validation result maps:
```clojure
[{"rule_id" "rule_001_v1"
  "status" "PASS"|"FAIL"|"NORUN"
  "message" "..."
  "execution_time_ms" 123
  ...}]
```

### discover-rules

Discover applicable rules for an entity type and schema.

**Arguments:**
- `entity-type` - String entity type
- `schema-url` - String schema URL (file://, http://, https://)
- `ruleset-name` - String ruleset name

**Returns:**
Vector of rule metadata maps:
```clojure
[{"rule_id" "rule_001_v1"
  "description" "..."
  "validates" "loan"
  "required_data" [...]
  "field_dependencies" [...]
  "applicable_schemas" [...]
  ...}]
```

### batch-validate

Execute validation for multiple entities with inline data.

**Arguments:**
- `entities` - Vector of entity maps `[{"entity_type" "loan" "entity_data" {...}}]`
- `id-fields` - Map of schema-url to id-field `{"<schema>" "loan_number"}`
- `ruleset-name` - String ruleset name

**Returns:**
Vector of per-entity result maps:
```clojure
[{"entity_type" "loan"
  "entity_id" "LN-001"
  "status" "completed"|"error"
  "results" [...]
  "summary" {...}}]
```

### batch-file-validate

Execute validation for entities loaded from file URI.

**Arguments:**
- `file-uri` - String URI (file://, http://, https://)
- `entity-types` - Map of schema-url to entity-type `{"<schema>" "loan"}`
- `id-fields` - Map of schema-url to id-field `{"<schema>" "loan_number"}`
- `ruleset-name` - String ruleset name

**Returns:**
Vector of per-entity result maps (same format as batch-validate)

## Use Cases

### Batch Jobs

Validate large datasets without HTTP overhead:

```clojure
(defn validate-daily-batch [service data-file]
  (let [results (.batch-file-validate
                  service
                  (str "file://" data-file)
                  {"file:///schemas/loan.schema.v1.0.0.json" "loan"}
                  {"file:///schemas/loan.schema.v1.0.0.json" "loan_number"}
                  "thorough")]
    ;; Process results
    (doseq [r results]
      (when (= "error" (get r "status"))
        (log/error "Validation failed" r)))))
```

### Streaming Pipelines

Inline validation in data pipelines:

```clojure
(defn process-loan-stream [service loan-stream]
  (->> loan-stream
       (map (fn [loan]
              (let [results (.validate service "loan" loan "quick")]
                (assoc loan :validation-results results))))
       (filter (fn [loan]
                 (every? #(= "PASS" (get % "status"))
                        (:validation-results loan))))))
```

### Testing

Test validation logic directly:

```clojure
(deftest test-loan-validation
  (let [config (load-test-config)
        service (vlib/create-service config)
        results (.validate service "loan" test-loan-data "quick")]

    (is (= 3 (count results)))
    (is (every? #(= "PASS" (get % "status")) results))

    (vlib/shutdown-service service)))
```

## Configuration

Library requires:
- `:python_runner` - Python runner executable and paths
- `:coordination_service` - External service for fetching related data

Does NOT require:
- Web server settings (port, host)
- CORS configuration
- Monitoring settings

## Thread Safety

`ValidationServiceImpl` is immutable and thread-safe. A single instance can be shared across threads:

```clojure
;; Create once at application startup
(def ^:private validation-service
  (vlib/create-service config))

;; Use from multiple threads safely
(defn validate-loan [loan]
  (.validate validation-service "loan" loan "quick"))
```

## Error Handling

Protocol methods throw `clojure.lang.ExceptionInfo` with `:type` key:
- `:pod-communication-error` - Failed to communicate with Python runner
- `:file-fetch-error` - Failed to fetch file from URI
- `:json-parse-error` - Failed to parse JSON
- `:validation-error` - Invalid parameters

```clojure
(try
  (.validate service "loan" loan-data "quick")
  (catch clojure.lang.ExceptionInfo e
    (case (:type (ex-data e))
      :pod-communication-error
        (log/error "Pod error:" (.getMessage e))
      :validation-error
        (log/error "Invalid params:" (ex-data e))
      (throw e))))
```

## Performance Tips

1. **Reuse service instance** - Creating a service initializes Python runner pods. Create once, reuse many times.

2. **Use batch operations** - Batch methods are more efficient than calling validate repeatedly:
   ```clojure
   ;; Good
   (.batch-validate service entities id-fields "quick")

   ;; Less efficient
   (map #(.validate service (:entity_type %) (:entity_data %) "quick") entities)
   ```

3. **Choose appropriate ruleset** - Use "quick" for fast validation, "thorough" when completeness matters more than speed.

4. **Pool configuration** - Adjust `:pool_size` in config based on workload:
   ```clojure
   {:python_runner {:pool_size 10  ;; More pods = higher throughput
                   :pool_max_idle_ms 300000}}
   ```

## Migration from Web API

If you're currently using the REST API, migration is straightforward:

### Before (HTTP):
```clojure
(defn validate-loan-http [loan]
  (http/post "http://validation-service:8080/api/v1/validate"
             {:body (json/write-str
                      {"entity_type" "loan"
                       "entity_data" loan
                       "ruleset_name" "quick"})
              :headers {"Content-Type" "application/json"}}))
```

### After (Library):
```clojure
(def service (vlib/create-service config))

(defn validate-loan-library [loan]
  (.validate service "loan" loan "quick"))
```

Benefits:
- No HTTP serialization overhead
- No network latency
- Direct access to validation data structures
- Simpler error handling
