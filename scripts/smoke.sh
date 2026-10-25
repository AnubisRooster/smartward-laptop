#!/bin/bash
# Read-only check of the RUNNING app (default http://localhost:8000): is everything answering?
#   scripts/smoke.sh [base-url]
BASE="${1:-http://localhost:8000}"; FAIL=0
check() {  # name, path, expected substring
  out=$(curl -s -m 8 "$BASE$2"); code=$?
  if [ $code -eq 0 ] && [[ "$out" == *"$3"* ]]; then echo "ok   $1"; else echo "FAIL $1 ($2)"; FAIL=1; fi
}
check "API status"            /api/status         '"model"'
check "Settings"              /api/settings       '"tts_engine"'
check "Sources"               /api/sources        '['
check "Articles"              '/api/articles?filter=all&limit=1' '"items"'
check "Projects"              /api/projects       '['
check "Natural voice status"  /api/tts/status     '"up"'
check "UI is served"          /                   '<div id="root">'
UP=$(curl -s -m 5 "$BASE/api/tts/status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('up'))" 2>/dev/null)
echo "info natural voice running: ${UP:-unknown}"
exit $FAIL
