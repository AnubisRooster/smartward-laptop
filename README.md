# SmartWard for Linux

Local-first research strategist, ported from the iPhone app. Everything runs on this laptop.

## Run

- Open **SmartWard** from the applications menu (or `~/SmartWardApp/bin/start_smartward.sh`). It is its own window with its own icon, not a browser tab.
  It starts and watches the API (`http://localhost:8000`) and the voice server, and restarts the API if it stops.
- **Closing the window keeps SmartWard running in the tray** (sources keep refreshing and indexing). The tray icon has Open, Refresh, Index now, Lock now and Quit; Quit stops the API and voice server too.
  Settings → This computer can start it at login (hidden in the tray).
- Browser version: `SMARTWARD_BROWSER=1 ~/SmartWardApp/bin/start_smartward.sh`. `start_smartward.sh stop` stops everything.
- Data lives in `~/.local/share/smartward/` (SQLite). Logs: `~/.local/state/smartward/api.log` (rotated).
- First time on a machine: `scripts/build_ui.sh`, `scripts/build_native.sh`, then `scripts/install_desktop.sh` (menu entry and icons).

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

## Hands-free chat (speech input)

The 🎙 button in Chat turns on hands-free: it listens through the microphone, sends each sentence when you pause, reads the answer aloud with the natural voice,
and listens again. Say “stop listening” to finish; “stop” cancels an answer in progress; when a tool needs approval it reads the request and you say “approve” or “decline”.
It never listens while it speaks, and it switches itself off when the window is hidden, the app locks, or you leave the chat. The microphone is open only while it is on.

Everything runs on this computer: `stt/listen.py` (microphone via `arecord`, a simple voice-activity detector, and Whisper through faster-whisper) is started by the API
only while hands-free is on, and stopped by it when the page stops asking. Install it once with `stt/setup.sh` (about 500 MB: the Python packages and the `small.en` model;
`MODEL=base.en stt/setup.sh` for a smaller one). English only with `.en` models.

## From your phone (Tailscale, no app store)

Settings → **Remote access** walks through it. The API still listens only on `127.0.0.1`; [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) publishes it to *your own devices* at
`https://<laptop>.<tailnet>.ts.net` (`tailscale serve --bg 127.0.0.1:8000`; never Funnel, which is public). On the phone you sign in once with a remote passphrase, then Add to Home Screen.

- **Off by default.** `sw/remote.py` is the front door: a request that came through the proxy must be from the allowed Tailscale account and Tailscale host name, carry a sign-in session
  (30-day cookie, `HttpOnly; Secure; SameSite=Strict`, stored hashed), and use only the phone allow-list. Phones can read, chat, talk and save links; they cannot change settings, back up, export, erase,
  change the app lock or sources, or touch the laptop's microphone. Five wrong passphrases lock sign-in for five minutes. Requests whose `Host` isn't a loopback name are refused even locally (DNS rebinding).
- **Talking from the phone.** The phone cuts what you say into sentences on the phone (`frontend/src/vad.ts`), sends each as a small WAV to `POST /api/voice/transcribe`, and the laptop's Whisper turns it into
  text (`stt/worker.py`). Nothing goes to Apple or Google. Answers are spoken by the natural voice through `/api/tts`.
- **Availability.** It works only while the laptop is awake and SmartWard is running. "Keep this laptop awake" holds a `systemd-inhibit` lock while remote access is on; closing the lid still suspends it.
- **Tests:** `tests/test_remote.py` (the front door, with each check proven to matter), `tests/test_remote_panel.py`, `tests/test_stt.py`.

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

## The native window

The window is a small Tauri shell (`frontend/src-tauri`): tray icon, single instance, process supervisor. The interface inside it is the web app the API serves from `ui/`,
so a front-end change only needs `scripts/build_ui.sh` (reload with Ctrl+R). Rebuild the shell with `scripts/build_native.sh` only when `src-tauri/` changes
(needs Rust, `libwebkit2gtk-4.1-dev`, `libayatana-appindicator3-dev`). The tray icon needs the GNOME "AppIndicator" extension (Ubuntu has it on by default).
The icon is drawn in `resources/icons/smartward.svg`; `npx tauri icon` regenerates the PNG/ICNS set from it.

**In the window:** Ctrl+K opens the command palette (go anywhere, run commands, search articles, themes, projects and chats); `?` lists the keyboard shortcuts;
drag a web link onto the window, or use the tray's "Save link from clipboard", to save a page. Desktop notifications (new matching articles, a failing source, a chat waiting
for approval) come from `POST /api/events/poll`, which the shell calls once a minute; each kind can be switched off in Settings → Notifications.
The light theme is generated from the dark palette by `scripts/gen_theme.py`; run it again only if the colours in use change.

## Development

The app is a Python API (`smartward_api.py`, `sw/`) plus a React front end (`frontend/`, built into `ui/`, which the API serves).
The natural voice lives in `tts/`. Your library is **not** in this folder: it is `~/.local/share/smartward/` (SQLite), and Settings → Backup & restore writes an encrypted copy.

| | |
|---|---|
| `scripts/check.sh` | Everything: the Python tests, shell syntax, front-end type check and Vitest tests. Run it before and after any change. (`--build` also rebuilds the UI.) |
| `python3 -m unittest discover -s tests -t .` | Only the Python tests (about 80, a few seconds). They use a throwaway data folder, no model, no network. |
| `scripts/build_ui.sh` | Rebuild the front end into `ui/` (reload the page; restart the API only if `sw/` or `smartward_api.py` changed). |
| `scripts/build_native.sh`, `scripts/install_desktop.sh` | Build the native window; install the menu entry and icons. `scripts/check.sh --native` also runs `cargo check`. |
| `scripts/smoke.sh` | Read-only check that the *running* app answers: API, settings, voice status, UI. Run it after restarting. |
| `bin/start_smartward.sh stop`, then start | Restart the API and voice server. |

**Updating the app.** Make a change, run `scripts/check.sh`, rebuild the UI if you touched `frontend/`, restart, run `scripts/smoke.sh`, then commit.
Back up first (Settings → Backup & restore) before anything that touches the database layout (`sw/db.py`).

**Keeping the features you use.** The tests cover: reading (filters, search, star/read), sources (validation, feed parsing, the private-network refusals),
the knowledge graph (rename/merge/split, digest), projects (brief history, suggestions, items, links), chat rules (which tools each mode gets, approvals, untrusted-text fencing),
export and encrypted backup/restore (private content, wrong passphrase), the app lock, usage and budget, and the natural voice. When you start relying on something new, add a test for it in `tests/`.

**Following the iPhone app.** This is a port, not a fork: upstream SmartWard changes do not arrive by themselves. Watch
[AnubisRooster/SmartWard](https://github.com/AnubisRooster/SmartWard) and port what you want, with a test.
