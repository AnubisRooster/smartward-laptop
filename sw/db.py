"""SQLite storage for SmartWard (articles, sources, graph, projects, chat, settings)."""
import json, os, sqlite3, threading, time
from contextlib import contextmanager

DATA_DIR = os.environ.get("SMARTWARD_DATA", os.path.expanduser("~/.local/share/smartward"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "smartward.db")
_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sources(
  id INTEGER PRIMARY KEY, kind TEXT, name TEXT, url TEXT, query TEXT, enabled INTEGER DEFAULT 1,
  etag TEXT, last_modified TEXT, last_status TEXT, last_error TEXT, last_fetched REAL,
  project_id INTEGER, system INTEGER DEFAULT 0, created REAL);
CREATE TABLE IF NOT EXISTS articles(
  id INTEGER PRIMARY KEY, source_id INTEGER, url TEXT UNIQUE, title TEXT, author TEXT, published REAL,
  teaser TEXT, text TEXT, full_text INTEGER DEFAULT 0, stage TEXT DEFAULT 'new', stage_error TEXT, fails INTEGER DEFAULT 0,
  relevance REAL, relevant INTEGER DEFAULT 1, starred INTEGER DEFAULT 0, read INTEGER DEFAULT 0,
  summary TEXT, summary_hash TEXT, graph_done INTEGER DEFAULT 0, graph_fails INTEGER DEFAULT 0,
  private INTEGER DEFAULT 0, project_id INTEGER, text_hash TEXT, created REAL, embedding BLOB);
CREATE INDEX IF NOT EXISTS ix_art_pub ON articles(published);
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(title, text, content='');
CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, article_id INTEGER, idx INTEGER, text TEXT, vec BLOB);
CREATE INDEX IF NOT EXISTS ix_chunk_art ON chunks(article_id);
CREATE TABLE IF NOT EXISTS themes(id INTEGER PRIMARY KEY, name TEXT, key TEXT UNIQUE, type TEXT, aliases TEXT DEFAULT '[]', created REAL, pinned_by TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS mentions(id INTEGER PRIMARY KEY, article_id INTEGER, theme_id INTEGER, chunk_idx INTEGER DEFAULT 0, source_kind TEXT DEFAULT 'article', ts REAL);
CREATE INDEX IF NOT EXISTS ix_men_art ON mentions(article_id); CREATE INDEX IF NOT EXISTS ix_men_theme ON mentions(theme_id);
CREATE TABLE IF NOT EXISTS edges(id INTEGER PRIMARY KEY, a INTEGER, b INTEGER, relation TEXT, article_id INTEGER, ts REAL);
CREATE INDEX IF NOT EXISTS ix_edge_a ON edges(a); CREATE INDEX IF NOT EXISTS ix_edge_b ON edges(b);
CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT, goal TEXT DEFAULT '', brief TEXT DEFAULT '', pending_brief TEXT, pending_reason TEXT, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS brief_history(id INTEGER PRIMARY KEY, project_id INTEGER, brief TEXT, note TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS domains(id INTEGER PRIMARY KEY, name TEXT, keywords TEXT DEFAULT '[]', created REAL);
CREATE TABLE IF NOT EXISTS developments(id INTEGER PRIMARY KEY, article_id INTEGER, kind TEXT, subject TEXT, claim TEXT, metric TEXT, value TEXT, baseline TEXT, evidence TEXT, domains TEXT DEFAULT '[]', quote TEXT, grounded INTEGER DEFAULT 0, ts REAL, created REAL, model TEXT);
CREATE INDEX IF NOT EXISTS ix_dev_art ON developments(article_id);
CREATE TABLE IF NOT EXISTS development_runs(article_id INTEGER PRIMARY KEY, ts REAL, status TEXT, model TEXT, n INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS hypotheses(id INTEGER PRIMARY KEY, project_id INTEGER, headline TEXT, implication TEXT, direction TEXT, confidence TEXT, evidence TEXT DEFAULT '[]', counter TEXT DEFAULT '[]', falsifier TEXT, action TEXT, status TEXT DEFAULT 'new', reason TEXT, item_id INTEGER, created REAL, updated REAL, model TEXT);
CREATE INDEX IF NOT EXISTS ix_hyp_proj ON hypotheses(project_id);
CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, project_id INTEGER, kind TEXT, text TEXT, done INTEGER DEFAULT 0, ts REAL);
CREATE TABLE IF NOT EXISTS project_links(id INTEGER PRIMARY KEY, project_id INTEGER, kind TEXT, url TEXT, private INTEGER DEFAULT 0, synced REAL, note TEXT);
CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY, title TEXT, mode TEXT, project_id INTEGER, off_record INTEGER DEFAULT 0, status TEXT DEFAULT 'idle', created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, conv_id INTEGER, role TEXT, content TEXT, meta TEXT DEFAULT '{}', ts REAL);
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, conv_id INTEGER, tool TEXT, title TEXT, detail TEXT, args TEXT, status TEXT DEFAULT 'pending', auto INTEGER DEFAULT 0, ts REAL);
CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY, ts REAL, feature TEXT, model TEXT, tokens_in INTEGER, tokens_out INTEGER, cost REAL, local INTEGER);
CREATE TABLE IF NOT EXISTS digests(id INTEGER PRIMARY KEY, created REAL, data TEXT);
CREATE TABLE IF NOT EXISTS memos(id INTEGER PRIMARY KEY, week TEXT UNIQUE, data TEXT, created REAL, model TEXT);
CREATE TABLE IF NOT EXISTS hypothesis_checks(id INTEGER PRIMARY KEY, hid INTEGER, ts REAL, verdict TEXT, supports TEXT DEFAULT '[]', contradicts TEXT DEFAULT '[]', seen TEXT DEFAULT '[]', note TEXT, model TEXT);
CREATE INDEX IF NOT EXISTS ix_hcheck ON hypothesis_checks(hid);
CREATE TABLE IF NOT EXISTS watches(id INTEGER PRIMARY KEY, name TEXT, terms TEXT DEFAULT '[]', domains TEXT DEFAULT '[]', sources TEXT DEFAULT '[]', min_evidence TEXT DEFAULT 'any', enabled INTEGER DEFAULT 1, scanned REAL, last_hit REAL, created REAL);
CREATE TABLE IF NOT EXISTS watch_hits(id INTEGER PRIMARY KEY, watch_id INTEGER, article_id INTEGER, dev_id INTEGER, ts REAL, notified INTEGER DEFAULT 0, UNIQUE(watch_id, article_id));
CREATE TABLE IF NOT EXISTS project_maps(project_id INTEGER PRIMARY KEY, text TEXT, updated REAL, model TEXT);
CREATE TABLE IF NOT EXISTS bench_runs(id INTEGER PRIMARY KEY, development_id INTEGER, plan TEXT, script TEXT, status TEXT, result TEXT, log TEXT, error TEXT, result_dev_id INTEGER, created REAL, started REAL, finished REAL, model TEXT);
CREATE TABLE IF NOT EXISTS removed_sources(id INTEGER PRIMARY KEY, source_id INTEGER, name TEXT, data TEXT, articles INTEGER, via TEXT, ts REAL, restored REAL);
CREATE TABLE IF NOT EXISTS push_subs(id INTEGER PRIMARY KEY, endpoint TEXT UNIQUE, keys TEXT, label TEXT, created REAL, last_ok REAL, fails INTEGER DEFAULT 0);
"""

def _connect():
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=OFF")
    return c

_conn = _connect()
with _lock:
    _conn.executescript(SCHEMA); _conn.commit()

def q(sql, args=(), one=False):
    with _lock:
        cur = _conn.execute(sql, args); rows = cur.fetchall()
    rows = [dict(r) for r in rows]
    return (rows[0] if rows else None) if one else rows

def x(sql, args=()):
    """Execute a write; returns lastrowid."""
    with _lock:
        cur = _conn.execute(sql, args); _conn.commit(); return cur.lastrowid

@contextmanager
def tx():
    with _lock:
        try:
            yield _conn
            _conn.commit()
        except Exception:
            _conn.rollback(); raise

DEFAULTS = {
    "model": os.environ.get("SMARTWARD_MODEL", "ollama_chat/llama3.2:3b"),
    "embed_model": "nomic-embed-text",
    "ollama_base": os.environ.get("OLLAMA_API_BASE", "http://localhost:11434"),
    "interests": "", "strictness": "balanced", "daily_budget": 1.0,
    "auto_approve": False, "onboarding_completed": False,
    "refresh_minutes": 60, "lock_enabled": False, "lock_after": 60, "lock_idle": 15,
    "voice_rate": 1.0, "voice_name": "", "digest_notify": False,
    "cloud_scope": "analysis", "analysis_model": "openrouter/poolside/laguna-s-2.1:free", "analysis_fallbacks": ["openrouter/recursive/flint-v1.0:free", "openrouter/cohere/north-mini-code:free"], "analysis_workers": 3, "remote_enabled": False, "remote_keep_awake": True, "remote_login": "", "remote_host": "", "remote_hash": "", "remote_sessions": {}, "remote_log": [], "notify_articles": True, "notify_sources": True, "notify_approvals": True, "notify_memo": True, "notify_watches": True, "memo_auto": False, "memo_day": 0, "push_daily_cap": 6, "design_model": "", "push_vapid_private": "", "push_vapid_public": "", "push_sent": {},
    # Natural read-aloud voice (Kokoro, on this machine). engine: auto | kokoro | browser
    "tts_engine": "auto", "tts_url": "http://127.0.0.1:8880", "tts_voice": "af_heart", "tts_profiles": {}, "tts_profile": "",
    "private_repo_local_only": True, "github_token": "", "lock_hash": "", "api_key": "",
}

def get_setting(key):
    r = q("SELECT value FROM settings WHERE key=?", (key,), one=True)
    if r is None: return DEFAULTS.get(key)
    try: return json.loads(r["value"])
    except Exception: return r["value"]

def set_setting(key, value):
    x("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

def all_settings(hide=("lock_hash", "github_token", "api_key", "remote_hash", "push_vapid_private")):
    out = dict(DEFAULTS)
    for r in q("SELECT key,value FROM settings"):
        try: out[r["key"]] = json.loads(r["value"])
        except Exception: out[r["key"]] = r["value"]
    for h in hide:
        if h in out: out[h] = bool(out[h])
    for k in ("remote_sessions", "remote_log"): out.pop(k, None)
    return out

def now(): return time.time()
