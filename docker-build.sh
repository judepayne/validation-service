#!/bin/bash
# Build and run validation service container

set -e

# Use docker if available, fall back to podman
if command -v docker &>/dev/null; then
  DOCKER=docker
elif command -v podman &>/dev/null; then
  DOCKER=podman
else
  echo "Error: neither docker nor podman found on PATH"
  exit 1
fi

IMAGE_NAME="validation-service"
TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${TAG}"
CONTAINER_NAME="validation-service"
PORT=8080

echo "=========================================="
echo "Validation Service - Docker Build Script"
echo "=========================================="
echo ""

# Build the image
echo "[1/3] Building image: ${FULL_IMAGE} (using ${DOCKER})"
${DOCKER} build -t ${FULL_IMAGE} .

echo ""
echo "[2/3] Removing old container (if exists)"
${DOCKER} rm -f ${CONTAINER_NAME} 2>/dev/null || true

echo ""
echo "[3/3] Running container: ${CONTAINER_NAME}"
${DOCKER} run -d \
  --name ${CONTAINER_NAME} \
  -p ${PORT}:8080 \
  ${FULL_IMAGE}

echo ""
echo "=========================================="
echo "✅ Container started successfully!"
echo "=========================================="
echo ""
echo "Service available at: http://localhost:${PORT}"
echo "Swagger UI: http://localhost:${PORT}/swagger-ui"
echo "Health check: http://localhost:${PORT}/health"
echo ""
echo "Commands:"
echo "  View logs:    docker logs -f ${CONTAINER_NAME}"
echo "  Stop:         docker stop ${CONTAINER_NAME}"
echo "  Remove:       docker rm ${CONTAINER_NAME}"
echo "  Shell access: docker exec -it ${CONTAINER_NAME} /bin/bash"
echo ""
echo "Waiting for service to be ready..."
sleep 5

# Health check
if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
    echo "✅ Service is healthy and responding!"
else
    echo "⚠️  Service may still be starting up. Check logs:"
    echo "   docker logs ${CONTAINER_NAME}"
fi
