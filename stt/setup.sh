#!/bin/bash
# Installs speech input for hands-free chat: a Python 3.10–3.13 environment, faster-whisper, and the Whisper model.
#   stt/setup.sh                    do it (about 500 MB, once)
#   MODEL=base.en stt/setup.sh      a smaller, less accurate model
#   SETUP_DRY_RUN=1 stt/setup.sh    print what it would do
# Needs `uv` (https://docs.astral.sh/uv/) or a python3.10–3.13 with the venv module, and ALSA's `arecord` (alsa-utils).
# Everything runs on this computer. The only download is the model, from Hugging Face, now.
set -e
cd "$(dirname "$0")"
MODEL="${MODEL:-small.en}"
run() { echo "+ $*"; [ -n "$SETUP_DRY_RUN" ] || "$@"; }

command -v arecord >/dev/null || echo "Note: arecord isn't installed (Ubuntu: sudo apt install alsa-utils); the microphone needs it." >&2
if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null; then
    run uv venv --python 3.13 .venv
    run uv pip install --python .venv/bin/python -r requirements.txt
  else
    PY=""; for p in python3.13 python3.12 python3.11 python3.10; do command -v $p >/dev/null && { PY=$p; break; }; done
    [ -n "$PY" ] || { echo "Need uv or Python 3.10–3.13." >&2; exit 1; }
    run $PY -m venv .venv
    run .venv/bin/pip install -r requirements.txt
  fi
fi
[ -n "$SETUP_DRY_RUN" ] || .venv/bin/python - "$MODEL" <<'PY'
import sys
from faster_whisper.utils import download_model
name = sys.argv[1]
path = download_model(name, output_dir=f"models/{name}")
print("Model ready:", path)
PY
echo "$MODEL" > model.txt
echo "Done. Turn on hands-free from the microphone button in Chat."
