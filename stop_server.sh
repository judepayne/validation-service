#!/bin/bash
# Stop the validation service by killing processes on port 8080

echo "=========================================="
echo "Stopping Validation Service"
echo "=========================================="
echo ""

# Find processes listening on port 8080
PIDS=$(lsof -ti :8080 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "No process found running on port 8080"
    echo "✓ Port is available"
else
    echo "Found process(es) on port 8080:"
    echo ""

    # Show process details
    lsof -i :8080 | grep LISTEN || true

    echo ""
    echo "Killing process(es): $PIDS"

    # Kill the processes
    kill -9 $PIDS 2>/dev/null || true

    # Wait a moment
    sleep 1

    # Verify they're gone
    if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "⚠️  Failed to stop some processes"
        exit 1
    else
        echo "✓ All processes stopped"
    fi
fi

echo ""
echo "Port 8080 is now free"
echo "=========================================="
