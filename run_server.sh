#!/bin/bash
# Start the validation service

set -e

JAR_FILE="target/validation-service-0.1.0-SNAPSHOT-standalone.jar"

echo "=========================================="
echo "Starting Validation Service"
echo "=========================================="
echo ""

# Check if port 8080 is already in use
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 8080 is already in use!"
    echo ""
    echo "To stop the existing process, run:"
    echo "  ./stop_server.sh"
    echo ""
    exit 1
fi

# Build jar if it doesn't exist
if [ ! -f "$JAR_FILE" ]; then
    echo "Uberjar not found, building..."
    echo ""
    clojure -T:build uber
    echo ""
    echo "✓ Build complete"
    echo ""
fi

# Start the server
echo "Starting server on http://localhost:8080"
echo "Using jar: $JAR_FILE"
echo ""
echo "Endpoints:"
echo "  - Health:     http://localhost:8080/health"
echo "  - Swagger UI: http://localhost:8080/swagger-ui"
echo "  - Validate:   POST http://localhost:8080/api/v1/validate"
echo ""
echo "To stop the server, press Ctrl+C or run:"
echo "  ./stop_server.sh"
echo ""
echo "=========================================="
echo ""

# Run the jar
java -jar "$JAR_FILE"
