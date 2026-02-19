(ns validation-service.utils.file-io
  "File I/O utilities for the web service."
  (:require [cheshire.core :as json]
            [clojure.java.io :as io]))

(defn write-json-file
  "Write data to JSON file.

  Args:
    file-path - Path to output file
    data - Data to write (will be serialized to JSON)

  Throws:
    IOException if file cannot be written"
  [file-path data]
  (with-open [writer (io/writer file-path)]
    (json/generate-stream data writer {:pretty true})))
