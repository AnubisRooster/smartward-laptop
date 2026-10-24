#!/bin/bash
# Usage: start_smartward.sh          -> API + UI in a browser window (default)
#        start_smartward.sh stop     -> stop the API
#        SMARTWARD_NATIVE=1 start_smartward.sh -> use the native Tauri window
APP_DIR="$HOME/SmartWardApp"
export PATH="$HOME/.local/bin:$PATH"
URL="http://localhost:8000/"
cd "$APP_DIR" || exit 1

if [ "$1" = "stop" ]; then pkill -f "$APP_DIR/smartward_api.py"; "$APP_DIR/tts/start.sh" stop; exit 0; fi

# Start the API unless our own copy is already serving the UI
if ! curl -s http://localhost:8000/status > /dev/null; then
  python3 "$APP_DIR/smartward_api.py" > "$APP_DIR/api.log" 2>&1 &
  API_PID=$!
  for i in $(seq 1 60); do
    curl -s http://localhost:8000/status > /dev/null && break
    if ! kill -0 $API_PID 2>/dev/null; then echo "API exited early; see $APP_DIR/api.log" >&2; exit 1; fi
    sleep 1
  done
fi

# Natural read-aloud voice (does nothing if it isn't installed or is already running)
"$APP_DIR/tts/start.sh"

if [ -n "$SMARTWARD_NATIVE" ]; then
  export GDK_BACKEND="${GDK_BACKEND:-x11}" WEBKIT_DISABLE_DMABUF_RENDERER=1
  exec "$APP_DIR/resources/smartward-ui-bin/smartward-ui"
fi

if command -v chromium >/dev/null; then exec chromium --app="$URL"
elif command -v google-chrome >/dev/null; then exec google-chrome --app="$URL"
elif command -v firefox >/dev/null; then exec firefox --new-window "$URL"
else exec xdg-open "$URL"; fi
