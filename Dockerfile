# Validation Service Dockerfile
# Multi-stage build for JVM service with Python runner

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

# Copy models directory (will be at /app/models)
COPY models/ models/

# Copy Python runner and its dependencies
COPY python-runner/ python-runner/

# Install Python dependencies
RUN pip3 install --no-cache-dir -r python-runner/requirements.txt

# Copy JVM service files
COPY jvm-service/config.edn jvm-service/
COPY jvm-service/resources jvm-service/resources/

# Copy the built uberjar from builder stage
COPY --from=builder /build/jvm-service/target/validation-service-0.1.0-SNAPSHOT-standalone.jar jvm-service/validation-service.jar

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
