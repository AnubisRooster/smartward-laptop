#!/bin/bash
# Natural read-aloud voice (Kokoro) on 127.0.0.1:8880 only.
#   tts/start.sh        start it if it isn't running
#   tts/start.sh stop   stop it
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/server.pid"

if [ "$1" = "stop" ]; then
  [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null; rm -f "$PIDFILE"; exit 0
fi

[ -x "$DIR/.venv/bin/python" ] || { echo "Natural voice isn't installed in $DIR" >&2; exit 0; }
curl -s -m 1 http://127.0.0.1:8880/health >/dev/null && exit 0

cd "$DIR" || exit 1
setsid nohup .venv/bin/python server.py --model kokoro-v1.0.onnx --voices voices-v1.0.bin > "$DIR/tts.log" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
