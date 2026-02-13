# Validation Service

This project is a POC business data validation service that assumes data in JSON format with JSON schema(s) for conformance. Example data uses Deals, Facilities & Loans - terminology from commercial banking, but the service will work for any data.

A Clojure web application mounts several endpoints for passing data to be validated. An RPC protocol is used to pass data to a Python rule runner. Python rules which are expected to be provided by business users, perhaps using AI, are run over the data to test its validity. The rules themselves are arbitrary. Each rule file is provided as a Python class that must implement a standard interface for a rule. Helper libraries are available to assist the rule writer to access fields in the data being validated. The helper libraries allow the rule writer to work at the logical model level and help separate the rule writer from model/ schema versioning. They also provide a means of tracking rule to field access dependencies; useful in model version management.

In the `docs/` folder are several documents on technical design, versioning, etc. `PRODUCTIONIZATION.md` covers the steps required to productize this application, for example to convert the Clojure web application to Java. This project has been deliberately provided with work to do in order that the implementing team will get to better know the application and its codebase. Expected productionization work (Clojure→Java conversion, gRPC migration): ~2 days with AI assistance and additional time for replacing the mocked up data examples and schema examples with real production data.

Each Python rule can return 'additional_data' which is context data required for more complex rules. e.g., a rule running on a Loan, can request its (parent) Facility and use both loan and facility data in the rule. To fetch the additional requested data, the Clojure/ Java part of the application calls a 'Coordination Service' that understands the relationships between different data entities in the broader business environment and how to fetch them to satisfy the rule. The Coordination service is NOT IMPLEMENTED and merely mocked up as a function call that returns nil. The Coordination service/ similar may/ may not be required in your business environment.

Config is used to organize Python rules into 'rulesets'. In use, different rulesets may be run under different circumstances, e.g., a 'quick' set for an inline preventative control and an 'EOD' set for more complex, long running rules which might for example call out to AI services for deeper analysis.

The application is containerized and ready to deploy to a development environment. Instructions below.

## API

The service exposes a REST API with the following endpoints:

**`POST /api/v1/validate`**
Validates a single entity against configured rules. Returns hierarchical validation results. (per rule results)

**`POST /api/v1/discover-rules`**
Returns metadata about available rules for a given entity type and schema, including field dependencies and applicable schema versions.

**`POST /api/v1/batch`**
Validates multiple entities in a single request. Supports mixed entity types with inline data. Flexible output modes (HTTP response or file output).

**`POST /api/v1/batch-file`**
Validates entities loaded from a file URI (supports file://, http://, https://). All entities must be the same type. Supports flexible output modes.

**`GET /health`**
Service health check endpoint.

**Interactive API Documentation:**
Once the container is running, explore and test the API using the OpenAPI interface at:
**http://localhost:8080/swagger-ui**

## Using as a Library

The validation service core logic can be embedded in other JVM applications without the HTTP layer. This is useful for:
- Batch jobs validating large datasets
- Streaming pipelines with inline validation
- Testing validation logic directly
- Embedding in other services

**Quick example:**

```clojure
(require '[validation-service.library.api :as vlib])

;; Create service instance
(def service (vlib/create-service library-config))

;; Validate an entity
(def results (.validate service "loan" entity-data "quick"))

;; Results is a vector of validation result maps
(println "Passed:" (count (filter #(= "PASS" (get % "status")) results)))
```

See [docs/LIBRARY-USAGE.md](docs/LIBRARY-USAGE.md) for complete documentation and examples.

## Configuration

The validation service uses a **two-tier configuration architecture** to separate infrastructure concerns from business logic:

### Tier 1: Infrastructure Configuration

**JVM Service** (`jvm-service/resources/library-config.edn`)
- Service infrastructure settings (Python runner path, timeouts, pool size)
- Coordination service settings (URL, retry logic, circuit breaker)
- Points to Python runner's local config

**Python Runner - Local Config** (`python-runner/local-config.yaml`)
- Infrastructure config owned by service team
- Points to business config location (can be remote URI)
- Cache settings for remote configs and rules
- Supports relative paths, `file://`, `http://`, and `https://` URIs

### Tier 2: Business Configuration

**Business Config** (`logic/business-config.yaml`)
- Business logic config owned by rules team
- Defines rule sets (quick/thorough) and their rule assignments
- Schema version to entity helper mappings
- Optional `rules_base_uri` for remote rule fetching
- Can live in a separate repository for production

### Development Setup

For local development, the default configuration uses local file paths:
```yaml
# python-runner/local-config.yaml
business_config_uri: "../logic/business-config.yaml"

# logic/business-config.yaml
# No rules_base_uri - rules loaded from logic/rules/ directory
```

### Production Setup

For production, point to remote configurations:
```yaml
# python-runner/local-config.yaml
business_config_uri: "https://rules-repo.example.com/prod/business-config.yaml"

# logic/business-config.yaml (in rules repository)
rules_base_uri: "https://rules-repo.example.com/prod/rules"
```

**Benefits:**
- **Separation of concerns:** Service team owns infrastructure, rules team owns business logic
- **Independent versioning:** Rules can be versioned and deployed separately from the service
- **Flexible deployment:** Different environments can point to different rule versions
- **Remote fetching:** Rules can be stored in artifact repositories (S3, HTTP servers, etc.)

# Schemas

schemas are JSON schema and live in the `logic/models` folder.

# Writing a rule

Rules live in `logic/rules/<entity-sub-folder>` (e.g., `logic/rules/loan/`, `logic/rules/facility/`, `logic/rules/deal/`) and must inherit from the base class. Each rule has the following interface:

`get_id` -> return the id of a rule (its filename minuse the .py extension)
`validates` -> return the name of the data entity type that the rule validates.
`required_data` -> returns the (names of) additional data entities required for the rule to run e.g. 'parent facility'
`description` -> plain english description of the rule
`set_required_data` -> for passing additional data into the rule class
`run` -> runs arbitrary logc defined in the rule

Lots more details in the docs!

## Container Quick Start

### Build

```bash
docker build -t validation-service .
```

### Run

```bash
docker run -d --name validation-service -p 8080:8080 validation-service
```

### Test

```bash
curl http://localhost:8080/health
```

**Swagger UI:** http://localhost:8080/swagger-ui

### Stop/Remove

```bash
docker stop validation-service
docker rm validation-service
```

## LICENSE

MIT © Jude Payne 2026
