#!/bin/bash
# Build and run validation service with Podman

set -e

IMAGE_NAME="validation-service"
TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${TAG}"
CONTAINER_NAME="validation-service"
PORT=8080

echo "=========================================="
echo "Validation Service - Podman Build Script"
echo "=========================================="
echo ""

# Build the image
echo "[1/3] Building image: ${FULL_IMAGE}"
podman build -t ${FULL_IMAGE} .

echo ""
echo "[2/3] Removing old container (if exists)"
podman rm -f ${CONTAINER_NAME} 2>/dev/null || true

echo ""
echo "[3/3] Running container: ${CONTAINER_NAME}"
podman run -d \
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
echo "  View logs:    podman logs -f ${CONTAINER_NAME}"
echo "  Stop:         podman stop ${CONTAINER_NAME}"
echo "  Remove:       podman rm ${CONTAINER_NAME}"
echo "  Shell access: podman exec -it ${CONTAINER_NAME} /bin/bash"
echo ""
echo "Waiting for service to be ready..."
sleep 5

# Health check
if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
    echo "✅ Service is healthy and responding!"
else
    echo "⚠️  Service may still be starting up. Check logs:"
    echo "   podman logs ${CONTAINER_NAME}"
fi
