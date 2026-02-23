# Validation Service Dockerfile
# Web API wrapper for validation-lib
#
# This service depends on validation-lib (installed via pip from GitHub)
# which provides the Python JSON-RPC validation engine.
# Business logic (rules, schemas, config) is fetched at runtime from
# the validation-logic GitHub repo via the URL in local-config.yaml.

FROM clojure:temurin-21-tools-deps-bookworm AS builder

# Set working directory for build
WORKDIR /build

# Copy dependency and build files first for better layer caching
COPY deps.edn .
COPY build.clj .

# Download dependencies (validation-lib will be cloned from GitHub)
RUN clojure -P
RUN clojure -P -T:build

# Copy source code
COPY src src/
COPY resources resources/

# Build uberjar
RUN clojure -T:build uber

# ============================================================================
# Runtime Stage
# ============================================================================

FROM eclipse-temurin:21-jre-jammy

# Install Python 3, pip, and curl
RUN apt-get update && \
    apt-get install -y python3 python3-pip curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Install validation-lib directly from GitHub (pinned to specific SHA for reproducibility)
RUN pip3 install --no-cache-dir git+https://github.com/judepayne/validation-lib.git@dd2a841

# Copy the built uberjar from builder stage
COPY --from=builder /build/target/validation-service-0.1.0-SNAPSHOT-standalone.jar app.jar

# Container directory structure:
# /app/
# ├── app.jar                      # Validation service uberjar
# └── web-config.edn               # Service configuration
#
# validation-lib is installed as a Python package via pip.
# Business logic is fetched at runtime from validation-logic on GitHub.

# Expose service port
EXPOSE 8080

# Environment variables
ENV JAVA_OPTS="-Xmx512m -Xms256m"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run the uberjar
CMD ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
