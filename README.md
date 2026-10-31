# SmartWard for Linux

A local-first research strategist. SmartWard follows the sources you choose, reads and scores what arrives, builds a knowledge graph of the themes, and turns the week's developments into what they may mean for your own projects. You discuss it all with a model that runs on your laptop. Nothing leaves the machine unless you pick a cloud model or open it from your phone.

It is a desktop app (a Tauri window with a tray icon) over a local Python API and a React interface. It started as a port of the [iPhone app](https://github.com/AnubisRooster/SmartWard).

## What it does

- **Reads for you.** RSS, arXiv, Hugging Face papers, Hacker News, GitHub releases and watched pages, with rate limits, robots.txt, de-duplication and relevance scores against your interests and projects. Summaries, a reader, and read-aloud.
- **Knowledge graph.** Themes, aliases and connections you can search, filter, rename, merge and split.
- **Developments and signals.** Pulls the measurable claims out of articles (what was measured, against what), and compares domains over time on the Radar.
- **Projects.** A brief with history, decisions, questions and actions, GitHub docs sync, and cited *implications*: hypotheses about what a development means for the project, which you accept or dismiss and which are later checked against new evidence.
- **Architecture maps.** Draft a project's architecture as text, score it against best-practice rules and a reviewer model, see developments placed on its parts, and export it as PNG, SVG, draw.io, Mermaid or plain text.
- **Weekly memo.** What shifted, what it may mean for each project, what to watch, written with checked citations. Share it as Markdown, HTML or Confluence source.
- **Watches and notifications.** Saved rules that match new articles; desktop notifications, and Web Push to your phone.
- **Chat.** Graph-aware chat with citations (brainstorm, critique, research plan, weekly review). Anything that fetches a page or saves something waits for your approval. Optional hands-free voice in and out.
- **Test bench.** Drafts a small script to test a claim on your laptop; it runs only after you approve it, in a `bwrap` sandbox with no access to your library or the internet.
- **Private by design.** Private items and off-the-record chats never go to a cloud model. Encrypted backup and restore, and an optional PIN app lock.

## Install

Ubuntu or similar, 8 GB RAM or more, about 6 GB free disk. Full steps, voice, free models and troubleshooting are in [HELP.md](HELP.md) (also in the app: **Settings → Help guide**).

```bash
sudo apt install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev build-essential pkg-config nodejs npm curl bubblewrap
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh        # Rust, to build the window
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b && ollama pull nomic-embed-text               # chat + embeddings
git clone https://github.com/AnubisRooster/smartward-laptop.git ~/SmartWardApp
cd ~/SmartWardApp
python3 -m pip install --break-system-packages -r requirements.txt
scripts/build_ui.sh && scripts/build_native.sh && scripts/install_desktop.sh
```

`bubblewrap` is only needed for the test bench. Optional extras:

- `tts/setup.sh`: a natural read-aloud voice (Kokoro, about 480 MB).
- `stt/setup.sh`: speech input for hands-free chat (Whisper, about 500 MB).

## Run

Open **SmartWard** from the applications menu, or:

```bash
~/SmartWardApp/bin/start_smartward.sh                     # the window
SMARTWARD_BROWSER=1 ~/SmartWardApp/bin/start_smartward.sh # a browser tab at http://localhost:8000 instead
~/SmartWardApp/bin/start_smartward.sh stop                # stop everything
```

It starts and watches the API and the voice server. Closing the window keeps it running in the tray, so sources keep refreshing; **Quit** in the tray menu stops it. **Settings → This computer** can start it at login. The first run walks you through checking Ollama and telling SmartWard what you follow.

Your library is in `~/.local/share/smartward/` (SQLite), not in the repository. Logs are in `~/.local/state/smartward/api.log`.

## Models

The default chat model is `ollama_chat/llama3.2:3b`; change it in Settings or with `SMARTWARD_MODEL`. A larger local model (for example `qwen2.5:7b`) gives better summaries and tool use. Cloud models work too, including OpenRouter's free ones: set the model id and key in Settings, and the daily budget applies. Architecture drafts and their review can use a separate, more capable model.

## From your phone

Off by default. Settings → **Remote access** walks you through it. [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) publishes the API to your own devices only (never Funnel); on the phone you sign in with a passphrase and add the page to your Home Screen.

A signed-in phone can read, chat, talk, refresh, write memos, edit projects, maps, sources and domains, and receive push notifications. It cannot change keys or addresses, back up, export, erase, change the app lock, approve test-bench runs or touch the laptop's microphone. It works only while the laptop is awake and SmartWard is running. The checks are in `sw/remote.py`, with tests in `tests/test_remote.py`.

## Development

Python API (`smartward_api.py`, `sw/`), React front end (`frontend/`, built into `ui/`, which the API serves), Tauri shell (`frontend/src-tauri`), voice in `tts/` and `stt/`.

| | |
|---|---|
| `scripts/check.sh` | Everything: Python tests, shell syntax, front-end type check and tests. `--build` also rebuilds the UI; `--native` also runs `cargo check`. Run it before and after a change. |
| `python3 -m unittest discover -s tests -t .` | Only the Python tests. They use a throwaway data folder, no model and no network. |
| `scripts/build_ui.sh` | Rebuild the front end into `ui/`. Reload the page; restart the API only if `sw/` or `smartward_api.py` changed. |
| `scripts/build_native.sh`, `scripts/install_desktop.sh` | Build the window; install the menu entry and icons. Rebuild the shell only when `frontend/src-tauri/` changes. |
| `scripts/smoke.sh` | Read-only check that the running app answers. Run it after a restart. |

Back up first (Settings → Backup & restore) before changing the database layout (`sw/db.py`), and never point a test at the real library. The iPhone app is a separate project: its changes don't arrive here by themselves.

**In the window:** Ctrl+K opens the command palette and `?` lists the keyboard shortcuts. The tray icon needs the GNOME AppIndicator extension (on by default in Ubuntu).
