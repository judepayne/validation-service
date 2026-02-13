# Production Migration Roadmap

**Status:** Phase 1 POC complete with library/web split and two-tier configuration architecture. Ready for production migration.

**POC Enhancements (Completed - February 2026):**
- ✅ **Library/Web Split** (Issue #1): JVM service separated into reusable library layer and HTTP web layer
- ✅ **Two-Tier Configuration** (Issue #2): Infrastructure config separate from business logic, supports remote rule fetching

---

## Critical Path Items

### 1. JVM Service Migration (Clojure → Java Spring Boot)

**Recommendation:** Use AI-assisted conversion (Claude, GPT-4, etc.)

**Note:** The POC already implements library/web separation (Issue #1), making migration easier.

- [ ] Convert library layer (`validation-service.library.*`) to Java
  - ValidationService interface already defined
  - Workflow orchestration logic already separated
  - ValidationRunnerClient protocol well-abstracted
- [ ] Convert web layer (`validation-service.api.*`) to Spring Boot
  - Map Reitit routes to @RestController
  - Replace Ring middleware with Spring interceptors
  - Port OpenAPI/Swagger annotations
- [ ] Migrate two-config architecture to Spring Boot
  - `library-config.edn` → `application-library.yml`
  - `web-config.edn` → `application-web.yml`
- [ ] Port ValidationRunnerClient protocol to Java interface
- [ ] Update dependency management (deps.edn → Maven/Gradle)
- [ ] Migrate integration tests to JUnit 5
- [ ] Add Spring Actuator for /health, /metrics endpoints
- [ ] Configure Logback with company logging standards

**Benefits of POC Architecture:**
- Clear separation simplifies parallel migration (library vs web)
- Library can be tested independently during migration
- Web layer can be migrated incrementally

**Estimated Effort:** 2-3 weeks with AI assistance (reduced from 3-4 weeks due to POC architecture)

---

### 2. Communication Protocol Migration (Pods → gRPC)

**Recommendation:** Use AI to generate gRPC definitions and boilerplate

- [ ] Define .proto file for validation service interface:
  - `GetRequiredData(EntityRequest) → RequiredDataResponse`
  - `Validate(ValidationRequest) → ValidationResponse`
  - `DiscoverRules(RulesRequest) → RulesMetadata`
- [ ] Generate Java client stubs (protoc + grpc-java)
- [ ] Generate Python server stubs (protoc + grpcio)
- [ ] Implement gRPC server in Python (replace bencode handler)
- [ ] Implement gRPC client in Java (replace pods client)
- [ ] Update error handling (gRPC status codes)
- [ ] Add connection pooling and retry logic
- [ ] Performance test vs. pods baseline

**Alternative:** Keep pods protocol if performance acceptable (<10ms overhead)

**Estimated Effort:** 1-2 weeks

---

### 3. Logging & Observability

**Company Standards Compliance:**

- [ ] Replace Clojure logging with SLF4J + Logback (Java)
- [ ] Structured logging (JSON format with correlation IDs)
- [ ] Integrate with company log aggregation (Splunk/ELK/etc.)
- [ ] Add distributed tracing (OpenTelemetry/Jaeger)
- [ ] Export metrics to Prometheus/Grafana
- [ ] Alert on error rates, latency P99, rule failures

**Key Metrics:**
- Request latency (P50, P95, P99)
- Rule execution time per rule_id
- Batch throughput (entities/sec)
- Error rates by endpoint and rule
- Pod/gRPC communication latency

---

### 4. Authentication & Authorization

- [ ] Integrate company SSO (OAuth2/OIDC)
- [ ] API key authentication for service-to-service calls
- [ ] Role-based access control (RBAC)
- [ ] Audit logging for all validation requests
- [ ] Rate limiting per client/API key

---

### 5. Scalability & Performance

**Horizontal Scaling:**
- [ ] Stateless service design (already achieved)
- [ ] Load balancer configuration (ALB/Nginx)
- [ ] Connection pooling for coordination service
- [ ] Consider async batch processing for large datasets (>10k entities)

**Python Runner:**
- ✅ **ConfigLoader:** Two-tier config with URI fetching and caching (Issue #2)
- ✅ **RuleFetcher:** Remote rule fetching with SHA256-based caching (Issue #2)
- [ ] Pod pooling (multiple Python processes for parallel processing)
  - Current: Single persistent pod (sufficient for POC)
  - Production: Pool of 5-10 pods for concurrent requests
  - Implementation guidance in `docs/POD-VS-GRPC.md`
- [ ] Process lifecycle management (health checks, graceful shutdown)
- [ ] Memory limits and monitoring
- [ ] Rule cache eviction strategy (currently immutable, cached forever)
  - Add TTL for cache entries
  - Add cache size limits with LRU eviction

**Database (if needed):**
- [ ] Persistent storage for validation results
- [ ] Schema migration strategy (Flyway/Liquibase)

---

### 6. Configuration Management

**Current Architecture (Issue #2 - Implemented):**
- ✅ **Two-tier configuration:** Infrastructure (`local-config.yaml`) separate from business logic (`business-config.yaml`)
- ✅ **Remote config support:** URI-based fetching (file://, http://, https://)
- ✅ **Caching:** Remote configs and rules cached with SHA256 keys
- ✅ **Separation of concerns:** Service team owns infrastructure, rules team owns business logic
- ✅ **Rules repository:** Top-level `rules/` directory can be separate repository

**Production Enhancements:**
- [ ] Externalize config URIs (Spring Cloud Config / Consul / AWS Parameter Store)
- [ ] Hot reload for rule set changes without service restart
  - Watch `business_config_uri` for changes
  - Reload ConfigLoader and RuleLoader dynamically
  - Clear rule cache on reload
- [ ] Environment-specific URIs (dev/staging/prod)
  ```yaml
  # local-config.yaml
  business_config_uri: "${BUSINESS_CONFIG_URI:../business-config.yaml}"
  rules_cache_dir: "${CACHE_DIR:/var/cache/validation-rules}"
  ```
- [ ] Config validation on startup (schema validation for both tiers)
- [ ] Version control for production configs (business-config.yaml in separate repo)
- [ ] Remote rule storage (S3, Azure Blob, HTTP server)
  ```yaml
  # business-config.yaml (production)
  rules_base_uri: "https://rules-cdn.example.com/v2.1/rules"
  ```

**Benefits of POC Architecture:**
- Already supports remote configs and rules
- Infrastructure/business separation enables independent deployment
- Rules team can deploy new rules without touching service
- Different environments can point to different rule versions

---

### 7. CI/CD Pipeline

- [ ] Build automation (Jenkins/GitLab CI/GitHub Actions)
- [ ] Automated testing (unit + integration)
- [ ] Docker image build and push to registry
- [ ] Kubernetes deployment manifests
- [ ] Blue-green or canary deployment strategy
- [ ] Automated rollback on failure

---

### 8. Container Orchestration (Kubernetes)

**Deployment:**
```yaml
# Example Kubernetes resources needed
- Deployment (3+ replicas for HA)
- Service (internal ClusterIP)
- Ingress (external access with TLS)
- HorizontalPodAutoscaler (CPU/memory based)
- ConfigMap (application config)
- Secret (credentials, API keys)
```

**Monitoring:**
- Liveness probe: `/health`
- Readiness probe: `/health/ready`
- Resource limits: CPU, memory
- Pod disruption budget for rolling updates

---

### 9. Data Model & Schema Management

**JSON Schema Versioning:**
- [ ] Schema registry (centralized storage)
- [ ] Version compatibility rules (breaking vs non-breaking changes)
- [ ] Schema evolution strategy
- [ ] Automated validation of schema changes

**Entity Helper Versioning:**
- Current: LoanV1, LoanV2 in separate files
- Production: Consider builder pattern or factory for version selection
- Document field mapping changes between versions

---

### 10. Coordination Service Integration

**Current:** Stubbed (returns empty map)

**Production:**
- [ ] Implement actual coordination service client
- [ ] Connection pooling and retry logic
- [ ] Circuit breaker for resilience (Hystrix/Resilience4j)
- [ ] Caching strategy for frequently accessed data
- [ ] Timeout configuration
- [ ] Fallback behavior when service unavailable

---

## POC Architecture Improvements

### Issue #1: Library/Web Split ✅ Complete

**Problem:** Monolithic JVM service mixing business logic with HTTP concerns.

**Solution Implemented:**
- **Library Layer** (`validation-service.library.*`)
  - `ValidationService` protocol with methods for validation operations
  - Workflow orchestration independent of transport
  - Configuration: `library-config.edn`
  - Zero HTTP dependencies
- **Web Layer** (`validation-service.api.*`)
  - HTTP handlers calling library protocol methods
  - Reitit routes with OpenAPI/Swagger
  - Configuration: `web-config.edn`
  - Middleware injecting ValidationService

**Production Benefits:**
- Library can be embedded in other JVM applications
- Easier migration to Java (clear boundaries)
- Independent testing of business logic
- Protocol methods return data, not HTTP responses

### Issue #2: Two-Tier Configuration ✅ Complete

**Problem:** Single configuration file mixing infrastructure and business logic, no support for remote rules.

**Solution Implemented:**

**Tier 1: Infrastructure Configuration**
- File: `python-runner/local-config.yaml`
- Owned by: Service team
- Contains: Python runner settings, business config URI, cache configuration
- Supports: Relative paths, file://, http://, https:// URIs

**Tier 2: Business Configuration**
- File: `business-config.yaml` (can be in separate repository)
- Owned by: Rules team
- Contains: Rule sets, schema mappings, rules base URI
- Supports: Remote rule fetching with URI-based paths

**Key Components:**
- `ConfigLoader`: Two-tier config loading with URI fetching and caching
- `RuleFetcher`: Remote rule fetching with SHA256-based caching
- `VersionRegistry`: Updated to support two-tier config

**Production Benefits:**
- **Separation of Concerns:** Service team owns infrastructure, rules team owns business logic
- **Independent Versioning:** Rules versioned and deployed separately from service
- **Remote Fetching:** Rules can be stored in artifact repositories (S3, HTTP servers)
- **Environment Flexibility:** Dev uses local paths, production uses remote URIs
- **Rules Repository:** Top-level `rules/` directory can be separate git repository

**Production Deployment Example:**
```yaml
# python-runner/local-config.yaml (production)
business_config_uri: "https://rules-cdn.example.com/prod/business-config.yaml"
rule_cache_dir: "/var/cache/validation-rules"

# business-config.yaml (hosted remotely, owned by rules team)
rules_base_uri: "https://rules-cdn.example.com/prod/rules"
quick_rules:
  "https://bank.example.com/schemas/loan/v1.0.0":
    - rule_id: rule_001_v1
    - rule_id: rule_002_v1
```

**Migration Impact:**
- Java Spring Boot can leverage two-tier config pattern
- Config can be externalized to Spring Cloud Config
- Rules team can deploy independently via CDN
- A/B testing and gradual rollouts simplified

---

## Testing Strategy

### Pre-Production
- [ ] Load testing (JMeter/Gatling) - target: 1000 req/sec
- [ ] Chaos testing (simulate pod failures, network issues)
- [ ] Security testing (OWASP top 10, penetration testing)
- [ ] Performance regression tests
- [ ] End-to-end testing with production-like data

### Production
- [ ] Canary deployment (1% traffic for 24h)
- [ ] Shadow traffic (parallel validation with old system)
- [ ] Gradual rollout (10% → 50% → 100%)

---

## Migration Timeline Estimate

| Phase | Duration | Description |
|-------|----------|-------------|
| **Phase 1: Core Migration** | 3-4 weeks | Clojure→Java, Pods→gRPC, logging setup |
| **Phase 2: Production Features** | 2-3 weeks | Auth, monitoring, config management |
| **Phase 3: Infrastructure** | 2-3 weeks | K8s setup, CI/CD, load testing |
| **Phase 4: Integration** | 2-3 weeks | Coordination service, end-to-end testing |
| **Phase 5: Deployment** | 1-2 weeks | Canary rollout, monitoring, validation |
| **Total** | **10-15 weeks** | Depends on team size and existing infrastructure |

---

## Decision Points

### Keep or Replace?

| Component | POC | Production Recommendation |
|-----------|-----|--------------------------|
| Bencode/Pods | ✅ Works | Consider gRPC for better tooling/monitoring |
| Single persistent pod | ✅ Works | Add pod pooling for >100 req/sec workloads |
| Two-tier config | ✅ Implemented (Issue #2) | **Keep** - Enables remote rules, supports production deployment |
| URI-based rule fetching | ✅ Implemented (Issue #2) | **Keep** - Already production-ready with caching |
| Library/Web split | ✅ Implemented (Issue #1) | **Keep** - Simplifies migration and enables reusability |
| JSON Schema | ✅ Works | Keep, add schema registry |
| Relative paths | ✅ Works | Keep, already container-ready |
| Entity helper versioning | ✅ Works | Keep, `version_registry.py` maps schemas to helpers |

---

## Open Questions

1. **Rule deployment frequency:** How often do rules change? (Impacts hot reload priority)
2. **Expected load:** Peak requests/sec? (Impacts scaling strategy)
3. **Data retention:** Store validation results long-term? (Impacts database needs)
4. **Multi-tenancy:** Multiple clients with isolated rule sets? (Impacts architecture)
5. **Compliance:** PCI/SOC2/GDPR requirements? (Impacts security controls)

---

## Contact & Resources

- **POC Documentation:** `TECHNICAL-DESIGN.md`
- **Container Guide:** `CONTAINER.md`
- **Entity Versioning:** `HOW-VERSIONING-WORKS.md`
- **Questions:** Contact architecture team

---

**Last Updated:** 2026-02-13
**Status:** Ready for production planning with enhanced POC architecture (Issues #1 and #2 complete)
