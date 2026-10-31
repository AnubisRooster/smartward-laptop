"""Bring back sources that were removed while their articles stayed, under their old numbers, so the articles are theirs again.

Twice now (24 and 30 October 2026) the GitHub release feeds and a few others vanished. Where the same feed had been added twice
(ids 6-11 on the 24th, re-added as 40-45 on the 30th), the older articles move to the newer source instead of making a duplicate.

    python3 scripts/restore_missing_sources.py            show what would change
    python3 scripts/restore_missing_sources.py --apply    back up the library, then change it
"""
import os, sqlite3, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sw import db  # noqa: E402

RESTORE = [  # (id, kind, name, url, query, enabled)
    (40, "github", "vllm-project/vllm releases", None, "vllm-project/vllm", 1),
    (41, "github", "sgl-project/sglang releases", None, "sgl-project/sglang", 1),
    (42, "github", "ggml-org/llama.cpp releases", None, "ggml-org/llama.cpp", 1),
    (43, "github", "ollama/ollama releases", None, "ollama/ollama", 1),
    (36, "rss", "Databricks blog", "https://www.databricks.com/feed", None, 1),
    (38, "manual", "arXiv papers (restored)", None, None, 0),
    (39, "manual", "Hugging Face papers (restored)", None, None, 0),
]
MERGE = {6: 40, 7: 41, 8: 42, 9: 43, 10: 44, 11: 45}       # an older copy of the same feed -> the one that stays


def main(apply):
    have = {r["id"] for r in db.q("SELECT id FROM sources")}
    count = lambda sid: db.q("SELECT COUNT(*) n FROM articles WHERE source_id=?", (sid,), one=True)["n"]
    for sid, kind, name, url, query, enabled in RESTORE:
        print(f"{'exists' if sid in have else 'restore'}: {sid} {name} ({count(sid)} articles waiting)")
    for old, new in MERGE.items():
        if old not in have: print(f"move {count(old)} articles from removed source {old} to {new}")
    if not apply: print("\nNothing changed. Run with --apply to do it."); return
    path = os.path.expanduser(f"~/SmartWardBackups/smartward-before-source-restore-{time.strftime('%Y%m%d-%H%M')}.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    src, dst = sqlite3.connect(db.DB_PATH), sqlite3.connect(path); src.backup(dst); dst.close(); src.close()
    print(f"backup: {path}")
    for sid, kind, name, url, query, enabled in RESTORE:
        if sid not in have:
            db.x("INSERT INTO sources(id,kind,name,url,query,enabled,system,created) VALUES(?,?,?,?,?,?,0,?)", (sid, kind, name, url, query, enabled, db.now()))
    for old, new in MERGE.items():
        if old not in have and db.q("SELECT 1 FROM sources WHERE id=?", (new,), one=True):
            db.x("UPDATE articles SET source_id=? WHERE source_id=?", (new, old))
    left = db.q("SELECT COUNT(*) n FROM articles WHERE source_id NOT IN (SELECT id FROM sources)", one=True)["n"]
    print(f"done; articles still without a source: {left}")


if __name__ == "__main__":
    main("--apply" in sys.argv)
