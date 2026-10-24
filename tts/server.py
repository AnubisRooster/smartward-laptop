#!/usr/bin/env python3
"""A small local text-to-speech server for `smartward read`.

Speaks the part of the OpenAI /v1/audio/speech API that SmartWard uses, backed
by Kokoro (82M parameters, Apache-2.0) through kokoro-onnx. It listens on
127.0.0.1 only, so article text never leaves this machine.

    python server.py --model kokoro-v1.0.onnx --voices voices-v1.0.bin
"""
import argparse
import glob
import io
import json
import os
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

import numpy as np


def prefer_system_espeak():
    """Use the distribution's espeak-ng when it is installed.

    The espeak-ng build bundled with `espeakng-loader` aborts here with
    "Error processing file '.../phontab'" even though its data is present, so
    the system library (package libespeak-ng1 with espeak-ng-data) is more
    reliable. Honors PHONEMIZER_ESPEAK_LIBRARY if you set it yourself.
    """
    if os.environ.get("PHONEMIZER_ESPEAK_LIBRARY"):
        return
    for pattern in ("/usr/lib/*/libespeak-ng.so.1", "/usr/lib64/libespeak-ng.so.1", "/usr/lib/libespeak-ng.so.1"):
        libraries = glob.glob(pattern)
        if not libraries:
            continue
        data = os.path.join(os.path.dirname(libraries[0]), "espeak-ng-data")
        if os.path.isdir(data):
            os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = libraries[0]
            os.environ.setdefault("PHONEMIZER_ESPEAK_DATA_PATH", data)
            return


prefer_system_espeak()
from kokoro_onnx import Kokoro  # noqa: E402  (after the espeak environment is set)


def to_wav(samples: np.ndarray, rate: int) -> bytes:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm.tobytes())
    return buffer.getvalue()


def make_handler(kokoro: Kokoro, default_voice: str):
    lock = Lock()  # one synthesis at a time keeps CPU use predictable

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, status: int, body: bytes, kind: str = "application/json"):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, b'{"status":"ok"}')
            elif self.path in ("/v1/voices", "/v1/audio/voices"):
                self._send(200, json.dumps({"voices": sorted(kokoro.get_voices())}).encode())
            else:
                self._send(404, b'{"error":"not found"}')

        def do_POST(self):
            if self.path != "/v1/audio/speech":
                return self._send(404, b'{"error":"not found"}')
            try:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length) or b"{}")
                text = str(request.get("input", "")).strip()
                if not text:
                    return self._send(400, b'{"error":"input is empty"}')
                voice = request.get("voice") or default_voice
                speed = float(request.get("speed", 1.0))
                with lock:
                    samples, rate = kokoro.create(text, voice=voice, speed=speed, lang="en-us")
                self._send(200, to_wav(samples, rate), "audio/wav")
            except Exception as error:  # report, don't crash the server
                self._send(500, json.dumps({"error": str(error)}).encode())

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="kokoro-v1.0.onnx")
    parser.add_argument("--voices", default="voices-v1.0.bin")
    parser.add_argument("--voice", default="af_heart", help="default voice")
    parser.add_argument("--port", type=int, default=8880)
    args = parser.parse_args()

    kokoro = Kokoro(args.model, args.voices)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(kokoro, args.voice))
    print(f"Kokoro speech server on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
