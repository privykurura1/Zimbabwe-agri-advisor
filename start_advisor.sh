#!/bin/bash
# Start Murimi Fara 2.0 on Mac/Linux: bash start_advisor.sh
# No AI model to load - it starts in seconds.
cd "$(dirname "$0")"
[ -d venv ] && source venv/bin/activate
# --host 0.0.0.0 lets phones on this computer's Wi-Fi use it too.
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 &
PID=$!
sleep 3
URL="http://127.0.0.1:8000/"
if which xdg-open > /dev/null; then xdg-open "$URL"
elif which open > /dev/null; then open "$URL"
else echo "Open $URL in your browser."; fi
echo "Murimi Fara is running. Press Ctrl+C to stop it."
wait $PID
