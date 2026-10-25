"""Shared setup for the tests.

Importing this module points SmartWard at a throwaway data folder and makes sure
nothing in a test can reach a model, the network or a background thread:

- SMARTWARD_DATA is a temp folder, so your real library is never touched;
- OLLAMA_API_BASE points at a port nothing listens on, so a stray model call fails fast;
- embeddings are off and background work (`bg`) does nothing;
- the TestClient is not used as a context manager, so the app's startup scheduler never runs.
"""
import atexit, io, json, os, shutil, sys, tempfile, threading, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import DATA      # noqa: E402  (importing the package already pointed SmartWard at a temp folder)

import smartward_api as api            # noqa: E402  (after the environment is set)
from sw import db, llm, tts            # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

api.bg = lambda fn, *a: None
llm.embed = lambda texts: None
client = TestClient(api.app)

ALL_TABLES = api.TABLES + ["settings", "approvals"]

# Belt and braces: never run against a real library, however the test modules were imported.
if os.path.realpath(db.DB_PATH) != os.path.realpath(os.path.join(DATA, "smartward.db")):
    raise RuntimeError(f"Refusing to run: the tests would use {db.DB_PATH}, not their own temporary library.")


def reset():
    """Empty every table, so each test starts from a blank library."""
    assert os.path.realpath(db.DB_PATH).startswith(os.path.realpath(tempfile.gettempdir())), "not a temporary library"
    from sw import awake; awake.release()
    with db.tx() as c:
        for t in ALL_TABLES:
            c.execute(f"DELETE FROM {t}")
        c.execute("INSERT INTO articles_fts(articles_fts) VALUES('delete-all')")


def add_source(name="Test feed", kind="rss", url="https://example.com/feed", **cols):
    sid = db.x("INSERT INTO sources(kind,name,url,enabled,system,created) VALUES(?,?,?,1,0,?)", (kind, name, url, db.now()))
    for k, v in cols.items():
        db.x(f"UPDATE sources SET {k}=? WHERE id=?", (v, sid))
    return sid


def add_article(source_id, title, text="", published=None, **cols):
    """An article that is already indexed for keyword search."""
    published = published if published is not None else db.now()
    aid = db.x("INSERT INTO articles(source_id,url,title,published,teaser,text,created,stage,relevant,relevance) VALUES(?,?,?,?,?,?,?,'done',1,0.5)",
               (source_id, f"https://example.com/{title.lower().replace(' ', '-')}-{db.now()}", title, published, text[:280], text, db.now()))
    db.x("INSERT INTO articles_fts(rowid,title,text) VALUES(?,?,?)", (aid, title, text))
    for k, v in cols.items():
        db.x(f"UPDATE articles SET {k}=? WHERE id=?", (v, aid))
    return aid


def tiny_wav(frames=240):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


class FakeSpeechServer:
    """Plays the part of the Kokoro server: /health, /v1/voices and /v1/audio/speech."""

    def __init__(self):
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _send(self, status, body, kind="application/json"):
                self.send_response(status); self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health": self._send(200, b"{}")
                elif self.path == "/v1/voices": self._send(200, json.dumps({"voices": ["bf_emma", "af_heart"]}).encode())
                else: self._send(404, b"{}")

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                outer.requests.append(body)
                self._send(200, tiny_wav(), "audio/wav")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown(); self.server.server_close()
