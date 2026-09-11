#!/bin/bash
# One-click launcher for Mudimu (Offline Farm Advisor) on Mac/Linux.
#
# Usage: double-click this file (if your file manager allows running
# scripts) or run: bash start_advisor.sh

cd "$(dirname "$0")"

echo "Starting Mudimu (Offline Farm Advisor)..."
echo ""

# Activate the virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Warning: venv not found. Trying to run with system Python instead."
fi

# Start the backend in the background, save its process ID so we can
# tell the user how to stop it later if needed.
uvicorn app:app --port 8000 &
BACKEND_PID=$!
echo "Advisor backend started (process ID: $BACKEND_PID)"

echo "Waiting for the advisor to start..."
sleep 5

# Open the interface in the default browser
if which xdg-open > /dev/null; then
    xdg-open index.html
elif which open > /dev/null; then
    open index.html
else
    echo "Please open index.html manually in your browser."
fi

echo ""
echo "Mudimu is running. Close this terminal or press Ctrl+C to stop the advisor."
wait $BACKEND_PID
