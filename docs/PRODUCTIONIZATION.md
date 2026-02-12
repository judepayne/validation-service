# Production Migration Roadmap

**Status:** Phase 1 POC complete. Ready for production migration.

---

## Critical Path Items

### 1. JVM Service Migration (Clojure → Java Spring Boot)

**Recommendation:** Use AI-assisted conversion (Claude, GPT-4, etc.)

- [ ] Convert Clojure handlers to Spring Boot @RestController
- [ ] Migrate Ring/Reitit routing to Spring Web MVC
- [ ] Replace Aero config with Spring Boot application.yml
- [ ] Port ValidationRunnerClient protocol to Java interface
- [ ] Update dependency management (deps.edn → Maven/Gradle)
- [ ] Migrate integration tests to JUnit 5
- [ ] Add Spring Actuator for /health, /metrics endpoints
- [ ] Configure Logback with company logging standards

**Estimated Effort:** 2-3 weeks with AI assistance

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
- [ ] Pod pooling (multiple Python processes for parallel processing)
- [ ] Process lifecycle management (health checks, graceful shutdown)
- [ ] Memory limits and monitoring

**Database (if needed):**
- [ ] Persistent storage for validation results
- [ ] Schema migration strategy (Flyway/Liquibase)

---

### 6. Configuration Management

- [ ] Externalize config (Spring Cloud Config / Consul / AWS Parameter Store)
- [ ] Hot reload for rule set changes (without service restart)
- [ ] Environment-specific configs (dev/staging/prod)
- [ ] Config validation on startup
- [ ] Version control for production configs

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
| File-based config | ✅ Works | Externalize to config service for hot reload |
| JSON Schema | ✅ Works | Keep, add schema registry |
| Relative paths | ✅ Works | Keep, already container-ready |

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

**Last Updated:** 2026-02-12
**Status:** Ready for production planning
