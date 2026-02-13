(ns validation-service.utils.file-io
  (:require [clojure.java.io :as io]
            [clj-http.client :as http]
            [cheshire.core :as json]
            [clojure.tools.logging :as log]))

(defn fetch-file-from-uri
  "Fetch content from file://, http://, or https:// URI.

  Args:
    uri - URI string (e.g., 'file:///data/loans.json', 'https://example.com/data.json')

  Returns:
    String content of the file

  Throws:
    ExceptionInfo with :type :file-fetch-error on failure"
  [uri]
  (try
    (let [url (io/as-url uri)
          protocol (.getProtocol url)]
      (case protocol
        "file" (slurp url)
        ("http" "https")
          (:body (http/get uri {:as :text
                               :throw-exceptions true
                               :socket-timeout 30000
                               :connection-timeout 10000}))
        (throw (ex-info "Unsupported URI scheme"
                       {:type :file-fetch-error
                        :uri uri
                        :supported-schemes ["file" "http" "https"]}))))
    (catch Exception e
      (log/error e "Failed to fetch file" {:uri uri})
      (throw (ex-info "Failed to fetch file from URI"
                     {:type :file-fetch-error
                      :uri uri
                      :error (.getMessage e)}
                     e)))))

(defn parse-json-array
  "Parse JSON array from string.

  Args:
    json-str - JSON string containing an array

  Returns:
    Vector of maps (preserves string keys)

  Throws:
    ExceptionInfo with :type :json-parse-error on failure"
  [json-str]
  (try
    (let [parsed (json/parse-string json-str)]
      (when-not (sequential? parsed)
        (throw (ex-info "Expected JSON array, got object or primitive"
                       {:type :json-parse-error})))
      (vec parsed))
    (catch Exception e
      (log/error e "Failed to parse JSON array")
      (throw (ex-info "Failed to parse JSON array"
                     {:type :json-parse-error
                      :error (.getMessage e)}
                     e)))))

(defn write-json-file
  "Write data structure to JSON file.

  Args:
    file-path - Absolute path to output file
    data - Data structure to write (will be JSON-encoded)

  Throws:
    ExceptionInfo with :type :file-write-error on failure"
  [file-path data]
  (try
    ;; Create parent directory if needed
    (let [parent-dir (-> file-path io/file .getParentFile)]
      (when (and parent-dir (not (.exists parent-dir)))
        (.mkdirs parent-dir)))

    (spit file-path
          (json/generate-string data {:pretty true}))
    (log/info "Wrote JSON file" {:path file-path})

    (catch Exception e
      (log/error e "Failed to write JSON file" {:path file-path})
      (throw (ex-info "Failed to write JSON file"
                     {:type :file-write-error
                      :path file-path
                      :error (.getMessage e)}
                     e)))))

(defn normalize-file-uri
  "Convert relative file:// URIs to absolute paths.

  Python's urllib cannot resolve relative file:// URIs properly, treating
  file://../models/file.json as /models/file.json instead of resolving
  relative to the current working directory.

  This function converts relative file:// URIs to absolute file:/// URIs
  by resolving them against the current working directory.

  Args:
    uri - URI string (e.g., 'file://../models/schema.json')

  Returns:
    Normalized URI with absolute path (e.g., 'file:///absolute/path/models/schema.json')

  Detection of relative vs absolute file URIs:
    - file:///absolute/path -> absolute (3 slashes after file:)
    - file://../relative/path -> relative (2 slashes, contains ..)
    - file://../../relative/path -> relative (2 slashes, contains ..)
    - file:./relative/path -> relative (no slashes, starts with .)
    - http://example.com/data.json -> not a file URI (unchanged)

  Examples:
    - file:///absolute/path/file.json -> file:///absolute/path/file.json (unchanged)
    - file://../logic/models/schema.json -> file:///Users/jude/Dropbox/Projects/validation-service/logic/models/schema.json
    - file://../../logic/models/schema.json -> file:///Users/jude/Dropbox/Projects/validation-service/logic/models/schema.json
    - file:./test/data.json -> file:///Users/jude/Dropbox/Projects/validation-service/jvm-service/test/data.json
    - http://example.com/data.json -> http://example.com/data.json (unchanged)"
  [uri]
  (if (and uri (.startsWith uri "file:"))
    (try
      ;; Determine if URI is relative by checking the original string
      (let [is-absolute? (.startsWith uri "file:///")
            is-relative? (or (.startsWith uri "file://..")
                           (.startsWith uri "file:."))]
        (if (or is-absolute? (not is-relative?))
          ;; Already absolute or unable to determine, return as-is
          uri
          ;; Relative path - extract path and resolve to absolute
          (let [path-str (cond
                          (.startsWith uri "file://") (subs uri 7)  ; Remove "file://"
                          (.startsWith uri "file:") (subs uri 5)    ; Remove "file:"
                          :else uri)
                absolute-file (-> path-str io/file .getCanonicalFile)
                absolute-path (.getAbsolutePath absolute-file)]
            (str "file://" absolute-path))))
      (catch Exception e
        (log/warn e "Failed to normalize file URI, returning as-is" {:uri uri})
        uri))
    ;; Not a file:// URI, return as-is
    uri))
