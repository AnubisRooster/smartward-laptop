"""Stands in for stt/listen.py: says ready, then one sentence, then echoes what it is told."""
import json, sys
print(json.dumps({"type": "ready"}), flush=True)
print(json.dumps({"type": "text", "text": "hello strategist", "ms": 5}), flush=True)
for line in sys.stdin:
    c = line.strip()
    if c == "quit": break
    print(json.dumps({"type": "state", "state": "paused" if c == "pause" else "listening"}), flush=True)
