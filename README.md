# SmartWard for Linux

Local-first research strategist, ported from the iPhone app. Everything runs on this laptop.

## Run

- Menu icon **SmartWard**, or `~/SmartWardApp/bin/start_smartward.sh`
  - Starts the API (`http://localhost:8000`) and opens the app in Firefox/Chromium.
  - `SMARTWARD_NATIVE=1 ~/SmartWardApp/bin/start_smartward.sh` uses the native Tauri window instead.
  - `~/SmartWardApp/bin/start_smartward.sh stop` stops the API.
- Data lives in `~/.local/share/smartward/` (SQLite). Logs: `~/SmartWardApp/api.log`.

## Requirements

```bash
sudo apt install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev build-essential pkg-config nodejs npm
python3 -m pip install --break-system-packages -r requirements.txt
ollama pull llama3.2:3b && ollama pull nomic-embed-text   # chat + on-device embeddings
```

## Natural read-aloud voice

Read-aloud (Reader, Today's brief and digest, chat replies) uses a natural voice, [Kokoro](https://github.com/thewh1teagle/kokoro-onnx),
running on this laptop in `~/SmartWardApp/tts/` (CPU, about 480 MB with its model). It starts with the app
(`start_smartward.sh`) and listens on `127.0.0.1:8880` only; article text never leaves the machine.
If it isn't running, the browser's own voice reads instead.

**Settings → Voice** lets you choose the engine (Automatic, Natural or Browser), the voice (54 voices, with a Listen button),
the speaking rate, and **reading profiles**: named voice-and-speed combinations such as a calm evening reader and a fast commute one.
The profile in use replaces the voice and rate above.

- Install it on a new machine with `tts/setup.sh` (needs `uv` or Python 3.10–3.13, and the system's `libespeak-ng1`).
- Start or stop it by hand: `~/SmartWardApp/tts/start.sh` / `~/SmartWardApp/tts/start.sh stop` (log: `tts/tts.log`).
- It uses your system's espeak-ng (`libespeak-ng1`, `espeak-ng-data`).
- The native Tauri window (`SMARTWARD_NATIVE=1`) was not rebuilt for this change; use the browser window, or rebuild it (see below).

## Models

Default chat model `ollama_chat/llama3.2:3b`; override in Settings or with `SMARTWARD_MODEL`.
A larger local model (e.g. `qwen2.5:7b`) gives better summaries and tool use.
A cloud model works too: set its litellm id and API key in Settings; the daily budget then applies.

## What carried over from the iPhone app

Today digest · Reading (unread/starred/all, relevance %, search, reader, five-question summary, read aloud) ·
Sources (RSS, arXiv, Hugging Face papers, Hacker News, GitHub releases, watched pages; rate limits, robots.txt,
conditional GET, dedupe, failure help) · knowledge graph (themes, aliases, rename/merge/split, decay) ·
GraphRAG chat with citations (brainstorm, critique, research plan, weekly review) with approval cards ·
Projects (brief with diff suggestions + history, decisions/questions/actions, links, GitHub docs sync, related reading) ·
onboarding · cost controls · export (JSON, GraphML, Markdown) · encrypted backup/restore · PIN app lock.

## Not carried over (needs Apple platform features)

Face ID/Touch ID, iOS background tasks (it refreshes while the app is running instead), Siri/Shortcuts/CarPlay,
share sheet (use the bookmarklet or "Save a page"), voice navigation by speech recognition,
Apple Foundation Models (a local Ollama model is used instead).

## Build the native window (optional)

```bash
cd ~/SmartWardApp/frontend && . ~/.cargo/env && npm run tauri build -- --no-bundle
cp src-tauri/target/release/smartward-ui ~/SmartWardApp/resources/smartward-ui-bin/
scripts/build_ui.sh        # the browser version served by the API
```

## Development

The app is a Python API (`smartward_api.py`, `sw/`) plus a React front end (`frontend/`, built into `ui/`, which the API serves).
The natural voice lives in `tts/`. Your library is **not** in this folder: it is `~/.local/share/smartward/` (SQLite), and Settings → Backup & restore writes an encrypted copy.

| | |
|---|---|
| `scripts/check.sh` | Everything: the Python tests, shell syntax, front-end type check. Run it before and after any change. (`--build` also rebuilds the UI.) |
| `python3 -m unittest discover -s tests -t .` | Only the Python tests (about 60, a few seconds). They use a throwaway data folder, no model, no network. |
| `scripts/build_ui.sh` | Rebuild the front end into `ui/` (reload the page; restart the API only if `sw/` or `smartward_api.py` changed). |
| `scripts/smoke.sh` | Read-only check that the *running* app answers: API, settings, voice status, UI. Run it after restarting. |
| `bin/start_smartward.sh stop`, then start | Restart the API and voice server. |

**Updating the app.** Make a change, run `scripts/check.sh`, rebuild the UI if you touched `frontend/`, restart, run `scripts/smoke.sh`, then commit.
Back up first (Settings → Backup & restore) before anything that touches the database layout (`sw/db.py`).

**Keeping the features you use.** The tests cover: reading (filters, search, star/read), sources (validation, feed parsing, the private-network refusals),
the knowledge graph (rename/merge/split, digest), projects (brief history, suggestions, items, links), chat rules (which tools each mode gets, approvals, untrusted-text fencing),
export and encrypted backup/restore (private content, wrong passphrase), the app lock, usage and budget, and the natural voice. When you start relying on something new, add a test for it in `tests/`.

**Following the iPhone app.** This is a port, not a fork: upstream SmartWard changes do not arrive by themselves. Watch
[AnubisRooster/SmartWard](https://github.com/AnubisRooster/SmartWard) and port what you want, with a test.
