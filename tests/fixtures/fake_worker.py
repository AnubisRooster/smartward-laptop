"""Stands in for stt/worker.py: says ready, then answers each request with the file's size."""
import json, os, sys
print(json.dumps({"id": 0, "ready": True}), flush=True)
for line in sys.stdin:
    r = json.loads(line)
    if not os.path.exists(r["path"]): print(json.dumps({"id": r["id"], "error": "missing"}), flush=True); continue
    print(json.dumps({"id": r["id"], "text": f"heard {os.path.getsize(r['path'])} bytes as {os.path.splitext(r['path'])[1]}"}), flush=True)
