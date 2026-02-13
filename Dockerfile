# Validation Service Dockerfile
# Multi-stage build for JVM service with Python runner
#
# Architecture:
# - JVM Service: Library/Web split (Issue #1)
#   - library-config.edn: Python runner, coordination service config
#   - web-config.edn: HTTP server, CORS, logging config
# - Python Runner: Two-tier configuration (Issue #2)
#   - local-config.yaml: Infrastructure config (Tier 1)
#   - logic/business-config.yaml: Business logic config (Tier 2, can be remote)
#   - logic/rules/: Rules directory (can be separate volume)
#   - logic/models/: JSON schemas
#
# Production Options:
# Option A: Bake logic/ into the image (default, as below)
# Option B: Mount logic/ as a volume from a separate repository
# Option C: Omit logic/ entirely and set business_config_uri to a remote URL —
#           LogicPackageFetcher will fetch the entire logic package into a local cache.
#           This is the recommended production approach for independent rule deployment.
#           Example: business_config_uri: "https://rules-cdn.example.com/prod/logic/business-config.yaml"

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

# Copy logic directory (business config, rules, models, entity helpers)
# In production Option C, this COPY can be removed — LogicPackageFetcher handles remote fetching.
COPY logic/ logic/

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
# ├── logic/                         # Business logic (can be separate repo)
# │   ├── business-config.yaml       # Business logic config (Tier 2)
# │   ├── rules/                     # Validation rules
# │   │   └── loan/, facility/, deal/
# │   └── models/                    # JSON schemas
# ├── python-runner/
# │   ├── local-config.yaml          # Infrastructure config (Tier 1)
# │   ├── core/                      # Core modules (ConfigLoader, LogicPackageFetcher, etc.)
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
