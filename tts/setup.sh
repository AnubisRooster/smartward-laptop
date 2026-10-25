#!/bin/bash
# Installs the natural voice: a Python 3.10–3.13 environment, the packages, and the Kokoro model files.
#   tts/setup.sh              do it
#   SETUP_DRY_RUN=1 tts/setup.sh   print what it would do
# Needs `uv` (https://docs.astral.sh/uv/) or a python3.10–3.13 with the venv module, plus curl.
# Also needs the system's espeak-ng (Ubuntu: sudo apt install libespeak-ng1 espeak-ng-data).
set -e
cd "$(dirname "$0")"
RELEASE="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
run() { echo "+ $*"; [ -n "$SETUP_DRY_RUN" ] || "$@"; }

if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null; then
    run uv venv --python 3.13 .venv
    run uv pip install --python .venv/bin/python -r requirements.txt
  else
    PY=""; for p in python3.13 python3.12 python3.11 python3.10; do command -v $p >/dev/null && { PY=$p; break; }; done
    [ -n "$PY" ] || { echo "Need uv or Python 3.10–3.13 (kokoro-onnx doesn't support 3.14 yet)." >&2; exit 1; }
    run $PY -m venv .venv
    run .venv/bin/pip install -r requirements.txt
  fi
fi
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [ -s "$f" ] || run curl -L --fail -o "$f" "$RELEASE/$f"
done
ls /usr/lib/*/libespeak-ng.so.1 >/dev/null 2>&1 || echo "Note: libespeak-ng1 isn't installed; the voice needs it." >&2
echo "Done. Start it with tts/start.sh (the app does this for you)."
