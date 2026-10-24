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
python3 -m pip install --break-system-packages litellm mcp pydantic trafilatura fastapi uvicorn cryptography numpy lxml httpx
ollama pull llama3.2:3b && ollama pull nomic-embed-text   # chat + on-device embeddings
```

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
cd ~/smartward-ui && . ~/.cargo/env && npm run tauri build -- --no-bundle
cp src-tauri/target/release/smartward-ui ~/SmartWardApp/resources/smartward-ui-bin/
rm -rf ~/SmartWardApp/ui && cp -r dist ~/SmartWardApp/ui   # the browser version served by the API
```
