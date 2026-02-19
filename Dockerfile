# Validation Service Dockerfile
# Web API wrapper for validation-lib
#
# This service depends on validation-lib which provides:
# - Python runner
# - Logic folder (rules, schemas, business config)
# - Core validation engine
#
# The Dockerfile clones validation-lib to get these components.

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

# Install Python 3, Git, and curl
RUN apt-get update && \
    apt-get install -y python3 python3-pip git curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Clone validation-lib (contains Python runner, logic folder)
RUN git clone https://github.com/judepayne/validation-lib.git && \
    cd validation-lib && \
    git checkout 69554f5fbbf03597a76272a4891ddbe884f4be0f

# Install Python dependencies for validation-lib
RUN pip3 install --no-cache-dir -r validation-lib/python-runner/requirements.txt

# Copy the built uberjar from builder stage
COPY --from=builder /build/target/validation-service-0.1.0-SNAPSHOT-standalone.jar app.jar

# Container directory structure:
# /app/
# ├── validation-lib/              # Cloned from GitHub
# │   ├── python-runner/
# │   │   ├── runner.py
# │   │   ├── local-config.yaml
# │   │   └── core/
# │   └── logic/
# │       ├── business-config.yaml
# │       ├── rules/
# │       └── models/
# ├── src/                         # This service's source
# │   └── validation_service/
# ├── resources/                   # This service's config
# │   ├── library-config.edn
# │   └── web-config.edn
# └── deps.edn

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
