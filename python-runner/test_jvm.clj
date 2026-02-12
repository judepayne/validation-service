(require '[babashka.pods :as pods])

(println "Loading pod from python-runner directory (same as bb test)...")
(pods/load-pod ["python3" "runner.py" "./config.yaml"])
(println "✓ Pod loaded")

(println "\nTrying get-required-data...")
(def result (pods/invoke "pod.validation-runner" 'get-required-data
                         {:entity_type "loan"
                          :schema_url "file:///Users/jude/Dropbox/Projects/validation-service/models/loan.schema.v1.0.0.json"
                          :ruleset_name "quick"}))

(println "✓ Result:" result)
(println "SUCCESS!")
(System/exit 0)
