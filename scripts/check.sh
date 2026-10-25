#!/bin/bash
# Runs every check before you trust a change.
#   scripts/check.sh           Python tests, shell syntax, front end type check
#   scripts/check.sh --build   ... and rebuild the UI the API serves (ui/)
set -e
cd "$(dirname "$0")/.."

echo "== Python tests"
python3 -m unittest discover -s tests -t .

echo "== Shell scripts parse"
for f in bin/*.sh scripts/*.sh tts/*.sh; do bash -n "$f" && echo "ok $f"; done

echo "== Front end type check"
[ -d frontend/node_modules ] || (cd frontend && npm ci)
(cd frontend && npx tsc --noEmit) && echo "ok"

if [ "$1" = "--build" ]; then scripts/build_ui.sh; fi
echo "All checks passed."
