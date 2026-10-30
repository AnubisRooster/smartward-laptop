#!/usr/bin/env python3
"""One-off repair after the library was restored from fragments: some articles ended up under the wrong source
(arXiv papers under "Enterprise AI", Hugging Face papers under "AI Alignment"). This moves them, by their web address, to sources that say what they are.

  scripts/fix_restored_sources.py            show what would change
  scripts/fix_restored_sources.py --apply    do it (take a backup first: Settings -> Backup & restore)

The new sources are switched off, so nothing is fetched; articles stay in Reading under the right name."""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sw import db

RULES = [  # (current source name, address pattern, new source name, kind)
    ("Enterprise AI", r"^https?://(www\.)?arxiv\.org/", "arXiv papers (restored)", "manual"),
    ("AI Alignment", r"^https?://huggingface\.co/papers/", "Hugging Face papers (restored)", "manual"),
]

def main(apply):
    moved = 0
    for src_name, pattern, new_name, kind in RULES:
        src = db.q("SELECT id FROM sources WHERE name=?", (src_name,), one=True)
        if not src: continue
        rows = [r for r in db.q("SELECT id,url FROM articles WHERE source_id=?", (src["id"],)) if re.search(pattern, r["url"] or "")]
        print(f"{len(rows):3d} articles from {src_name!r} look like {new_name!r}")
        if not rows or not apply: continue
        new = db.q("SELECT id FROM sources WHERE name=?", (new_name,), one=True)
        nid = new["id"] if new else db.x("INSERT INTO sources(kind,name,enabled,system,created) VALUES(?,?,0,0,?)", (kind, new_name, db.now()))
        for r in rows: db.x("UPDATE articles SET source_id=? WHERE id=?", (nid, r["id"]))
        moved += len(rows)
    print(f"moved {moved}" if apply else "(nothing changed; run with --apply)")

if __name__ == "__main__":
    main("--apply" in sys.argv)
