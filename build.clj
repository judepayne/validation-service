(ns build
  (:require [clojure.tools.logging :as log]
            [clojure.tools.build.api :as b]
            [clojure.java.io :as io]))

(def lib 'validation-service/validation-service)
(def version "0.1.0-SNAPSHOT")
(def class-dir "target/classes")
(def basis (b/create-basis {:project "deps.edn"}))
(def uber-file (format "target/%s-%s-standalone.jar" (name lib) version))

(defn clean [_]
  (b/delete {:path "target"}))

(defn- find-validation-lib-path
  "Find the path to validation-lib git dependency from basis."
  [basis]
  (let [libs (:libs basis)
        validation-lib-key (first (filter #(and (symbol? %)
                                                (= (str %) "validation-lib/validation-lib"))
                                         (keys libs)))
        lib-info (when validation-lib-key (get libs validation-lib-key))
        ;; Git dependencies use :deps/root for the base path
        lib-path (when lib-info (:deps/root lib-info))]
    lib-path))

(defn- copy-python-runner
  "Copy python-runner files from validation-lib git dependency into class-dir.

  This ensures python-runner is bundled in the uberjar even though it comes
  from a git dependency."
  [basis class-dir]
  (println "Copying python-runner from validation-lib to jar...")

  (let [validation-lib-path (find-validation-lib-path basis)]
    (when-not validation-lib-path
      (throw (ex-info "Could not find validation-lib in dependencies" {})))

    (println "  Found validation-lib at:" validation-lib-path)

    (let [python-files ["runner.py"
                        "requirements.txt"
                        "local-config.yaml"
                        "core/__init__.py"
                        "core/config_loader.py"
                        "core/logic_fetcher.py"
                        "core/rule_executor.py"
                        "core/rule_fetcher.py"
                        "core/rule_loader.py"
                        "core/validation_engine.py"
                        "transport/__init__.py"
                        "transport/base.py"
                        "transport/jsonrpc_transport.py"]
          source-base (io/file validation-lib-path "python-runner")]

      (doseq [file python-files]
        (let [source-file (io/file source-base file)
              target-file (io/file class-dir "python-runner" file)]
          (if (.exists source-file)
            (do
              (io/make-parents target-file)
              (io/copy source-file target-file)
              (println "  ✓" file))
            (println "  ⚠️  Warning: File not found:" (.getPath source-file)))))

      (println "Python runner copied successfully"))))

(defn- copy-logic
  "Copy logic/ directory from validation-lib git dependency into class-dir.

  This bundles the logic package (rules, schemas, entity helpers) in the JAR
  so it can be extracted at runtime alongside python-runner."
  [basis class-dir]
  (println "Copying logic/ from validation-lib to jar...")

  (let [validation-lib-path (find-validation-lib-path basis)]
    (when-not validation-lib-path
      (throw (ex-info "Could not find validation-lib in dependencies" {})))

    (let [logic-source (io/file validation-lib-path "logic")
          logic-target (io/file class-dir "logic")]

      (when-not (.exists logic-source)
        (throw (ex-info "logic/ directory not found in validation-lib"
                        {:path (.getPath logic-source)})))

      ;; Copy entire logic/ directory recursively
      (letfn [(copy-dir [source target]
                (when (.isDirectory source)
                  (.mkdirs target)
                  (doseq [file (.listFiles source)]
                    (let [target-file (io/file target (.getName file))]
                      (if (.isDirectory file)
                        (copy-dir file target-file)
                        (do
                          (io/copy file target-file)
                          (println "  ✓" (.getPath file))))))))]
        (copy-dir logic-source logic-target))

      (println "Logic directory copied successfully"))))

(defn uber [_]
  (println "Building uberjar:" uber-file)
  (clean nil)
  (b/copy-dir {:src-dirs ["src" "resources"]
               :target-dir class-dir})

  ;; Copy python-runner and logic from validation-lib dependency into jar
  (copy-python-runner basis class-dir)
  (copy-logic basis class-dir)

  (b/compile-clj {:basis basis
                  :ns-compile '[validation-service.core]
                  :class-dir class-dir})
  (b/uber {:class-dir class-dir
           :uber-file uber-file
           :basis basis
           :main 'validation-service.core})
  (println "Uberjar created successfully:" uber-file))
