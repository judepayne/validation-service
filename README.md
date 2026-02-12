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

## Configuration

**JVM Service** (`jvm-service/config.edn`)
Service configuration including port, Python runner path, and coordination service settings.

**Python Rule Runner** (`python-runner/config.yaml`)
Defines rule sets (quick/thorough), schema version mappings, and entity helper routing. Controls which rules execute for each entity type and schema version.

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
