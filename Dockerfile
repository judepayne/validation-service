# Validation Service Dockerfile
# Multi-stage build for JVM service with Python runner
#
# Architecture:
# - JVM Service: Library/Web split (Issue #1)
#   - library-config.edn: Python runner, coordination service config
#   - web-config.edn: HTTP server, CORS, logging config
# - Python Runner: Two-tier configuration (Issue #2)
#   - local-config.yaml: Infrastructure config (Tier 1)
#   - business-config.yaml: Business logic config (Tier 2, can be remote)
#   - rules/: Top-level rules directory (can be separate volume)
#
# Production Options:
# - Mount business-config.yaml as ConfigMap or volume
# - Mount rules/ directory from separate repository
# - Set business_config_uri to remote URL (S3, HTTP)
# - Set rules_base_uri to remote URL for rule fetching

FROM clojure:temurin-21-tools-deps-bookworm AS builder

# Set working directory for build
WORKDIR /build/jvm-service

# Copy dependency files first for better layer caching
COPY jvm-service/deps.edn .
COPY jvm-service/build.clj .

# Download dependencies
RUN clojure -P -M:build

# Copy source code
COPY jvm-service/src src/
COPY jvm-service/resources resources/

# Build uberjar
RUN clojure -T:build uber

# ============================================================================
# Runtime Stage
# ============================================================================

FROM eclipse-temurin:21-jre-jammy

# Install Python 3 and required packages
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create application directory structure
WORKDIR /app

# Copy business configuration (Tier 2 - can be mounted in production)
COPY business-config.yaml .

# Copy rules directory (top-level - can be separate repo/volume in production)
COPY rules/ rules/

# Copy models directory (will be at /app/models)
COPY models/ models/

# Copy Python runner and its dependencies (includes local-config.yaml)
COPY python-runner/ python-runner/

# Install Python dependencies
RUN pip3 install --no-cache-dir -r python-runner/requirements.txt

# Copy JVM service files (resources includes library-config.edn and web-config.edn)
COPY jvm-service/resources jvm-service/resources/

# Copy the built uberjar from builder stage
COPY --from=builder /build/jvm-service/target/validation-service-0.1.0-SNAPSHOT-standalone.jar jvm-service/validation-service.jar

# Container directory structure:
# /app/
# ├── business-config.yaml          # Business logic config (Tier 2)
# ├── rules/                         # Validation rules (top-level)
# │   └── loan/, facility/, deal/
# ├── models/                        # JSON schemas
# ├── python-runner/
# │   ├── local-config.yaml          # Infrastructure config (Tier 1)
# │   ├── core/                      # Core modules (ConfigLoader, RuleFetcher, etc.)
# │   └── ...
# └── jvm-service/                   # WORKDIR
#     ├── resources/
#     │   ├── library-config.edn     # Library layer config
#     │   └── web-config.edn         # Web layer config
#     └── validation-service.jar

# Set working directory to jvm-service (required for relative paths)
WORKDIR /app/jvm-service

# Expose service port
EXPOSE 8080

# Environment variables
ENV JAVA_OPTS="-Xmx512m -Xms256m"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run the service
CMD ["sh", "-c", "java $JAVA_OPTS -jar validation-service.jar"]
