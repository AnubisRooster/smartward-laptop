# SmartWard help guide

SmartWard is a local-first research strategist. It follows the sources you choose (feeds, arXiv, Hacker News, GitHub releases, web pages), reads and scores what arrives, builds a knowledge graph of the themes, and lets you discuss it all with a model that runs on your own laptop. Nothing leaves your computer unless you choose a cloud model or open it from your phone.

This guide covers installing it, setting it up, and the optional extras (voice, free cloud models, phone access). Commands go in a terminal.

## What you need

- A Linux laptop (these steps are written for Ubuntu) with about 6 GB of free disk space for the models, and 8 GB of RAM or more.
- [Ollama](https://ollama.com), which runs the language model on your computer.
- Python 3.10 or newer, Node.js with npm, and Rust (only to build the window).

## Install

1. Install the system packages:

```bash
sudo apt install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev build-essential pkg-config nodejs npm curl
```

2. Install Rust (needed once, to build the window). Accept the defaults:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

3. Install Ollama and download the two models SmartWard uses: a small chat model and an embedding model for search:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

4. Get SmartWard and install its Python packages:

```bash
git clone https://github.com/AnubisRooster/smartward-laptop.git ~/SmartWardApp   # a private repository: sign in with your GitHub account when asked
cd ~/SmartWardApp
python3 -m pip install --break-system-packages -r requirements.txt
```

5. Build the interface and the window, then add SmartWard to your applications menu:

```bash
scripts/build_ui.sh
scripts/build_native.sh
scripts/install_desktop.sh
```

The first build downloads packages and compiles the window, which takes several minutes. `install_desktop.sh` adds a **SmartWard** entry and icon for your user only (no sudo).

6. Open **SmartWard** from your applications menu. It starts its own background service and shows the welcome screen. For a browser tab instead of the window: `SMARTWARD_BROWSER=1 ~/SmartWardApp/bin/start_smartward.sh`, then open `http://localhost:8000`.

## First run

The welcome screen has three steps:

1. **Check** shows whether Ollama is running and the chat and embedding models are installed, with the command to fix each one.
2. **Tell me**: describe what you follow and what you are working on in a sentence or two (and paste any links). SmartWard asks your model to propose interests, projects and sources.
3. **Review**: untick anything you do not want, edit names and links, and press the button to apply. If the model cannot make a proposal you can fill the fields in by hand.

SmartWard then fetches your sources and starts reading. The first indexing pass takes a while; progress shows at the top.

## The pages

- **Today**: a digest of what matters, with a *Brief me* button that reads it aloud.
- **Reading**: the articles, with relevance scores, search, a reader, a five-question summary and read-aloud. Add a source from **Sources**.
- **Graph**: the themes found in what you read and chat about. Rename, merge and split themes to correct it.
- **Chat**: a strategist you can brainstorm with, critique an idea, plan research with, or use for a weekly review. It cites what you have read ([R1], [R2]) and asks your approval before it reads a page, follows a source or saves a note.
- **Projects**: a brief that SmartWard suggests updates to, plus decisions, open questions and actions, links (including GitHub repos) and related reading.
- **Quick tips**: Ctrl+K opens the command palette (go anywhere, search articles, run commands); `?` lists the keyboard shortcuts; drag a web link onto the window, or use the tray's *Save link from clipboard*, to save a page.

### Sources

In **Sources**, add: an RSS or Atom feed, an arXiv category, Hugging Face papers, a Hacker News search, a GitHub repository's releases, or a web page to watch. SmartWard respects robots.txt, rate-limits itself, and fetches only the newest 40 posts per source so a large archive cannot flood your library. A source that keeps failing shows what went wrong.

## Choosing the model

Open **Settings → Model**.

- **Chat model**: the default is `ollama_chat/llama3.2:3b`, a small model that runs well on a laptop. A larger one such as `ollama_chat/qwen2.5:7b` (after `ollama pull qwen2.5:7b`) gives better summaries and tool use but needs more memory and time. You can also enter any litellm model id under *Other model*.
- **Embedding model**: `nomic-embed-text`. Without it, search falls back to keywords.
- Press **Test the model** to send one tiny request and check the model answers.

### Free cloud models (OpenRouter)

Local models keep everything on your computer. For a stronger model at no cost, use [OpenRouter](https://openrouter.ai):

1. Create an account and an API key at [openrouter.ai/keys](https://openrouter.ai/keys).
2. In **Settings → Model**, paste the key into the API key field and save. It is stored only on this computer and is never shown back.
3. Open **OpenRouter free models** (in the same section) and show the list. Pick one and use it.

**Think before using it:** free models run on OpenRouter's servers, so your questions (and any library text the strategist includes) leave this computer, and free providers may keep them. By default an OpenRouter model answers chat only; background work stays on the local model unless you change it in Settings. Private repository content never goes to a cloud model.

For paid cloud models set a **daily budget** in *Usage & budget*: once it is spent, background work switches back to the local model.

## Voice (reading aloud and talking)

Read-aloud uses a natural voice ([Kokoro](https://github.com/thewh1teagle/kokoro-onnx)) that runs on your computer; hands-free chat listens through your microphone with Whisper, also on your computer. Install them once:

```bash
sudo apt install -y libespeak-ng1 espeak-ng-data alsa-utils
~/SmartWardApp/tts/setup.sh     # the voice, about 480 MB
~/SmartWardApp/stt/setup.sh     # speech input, about 500 MB (MODEL=base.en for a smaller one)
```

The voice server starts with the app and listens on `127.0.0.1:8880` only. If it is not installed, the browser's own voice reads aloud instead.

- **Settings → Voice**: choose the engine (Automatic, Natural, Browser), the voice (54, with a Listen button), the speaking rate, and *reading profiles* (named voice-and-speed combinations).
- **Hands-free chat**: press the microphone in Chat (or **Talk**). Say "stop" to interrupt, "stop listening" to finish, and "approve" or "decline" when a tool needs your approval. It never listens while it speaks, and the microphone closes when you leave the chat, lock the app or hide the window.

## Your data and privacy

- Everything is in a SQLite database: `~/.local/share/smartward/smartward.db`. Logs: `~/.local/state/smartward/api.log`.
- **Settings → App lock**: a PIN covers the whole app on launch, after you have left the window for a while (default 1 minute) and after a spell with no activity (default 15 minutes, or never). Typing, clicking, scrolling, moving the mouse, hands-free talking and waiting for an answer all count as activity, so it does not lock while you are using it. (The PIN is stored as a salted hash.)
- **Settings → Export**: your library as JSON, the graph as GraphML (opens in Gephi or yEd), projects as Markdown.
- **Settings → Backup & restore**: the whole library as one encrypted file (needs a passphrase of 8+ characters; keep it, it cannot be recovered). API keys, the GitHub token and the app lock are never included.
- **Settings → GitHub**: only needed for private repositories. Paste a read-only personal access token; SmartWard never writes to GitHub. You type the token yourself in Settings; it is stored on this computer only.

## Open it from your phone (Tailscale)

This reaches your laptop over your own private network. It is never on the public internet. The laptop must be on and running SmartWard.

1. Install [Tailscale](https://tailscale.com/download) on the laptop and on your phone, and sign in to the same account on both. In the Tailscale admin page, turn on **MagicDNS** and **HTTPS certificates**.
2. In SmartWard, open **Settings → Remote access**. Enter your Tailscale login (only that account may connect) and a **remote passphrase** (8+ characters, separate from the PIN), and press Save.
3. Publish SmartWard to your own devices. In a terminal on the laptop:

```bash
tailscale serve --bg 127.0.0.1:8000
```

Never use `tailscale funnel`: that is public. (If you also run Selfward, it uses its own port: `tailscale serve --bg --https=8443 127.0.0.1:8100`.)

4. Tick **Allow my phone to connect**. A QR code and the address appear (`https://<laptop>.<tailnet>.ts.net`).
5. On the phone, with Tailscale connected, scan the code or open the address, sign in with the passphrase, then **Add to Home Screen** (iPhone: Share → Add to Home Screen; Android: menu → Install app).

What to know:

- It is **off by default**, and sign-in lasts 30 days after you last use it. Settings shows the signed-in phones and lets you sign any of them out.
- A phone can read, chat, talk and save links. It cannot change settings, make backups or exports, erase anything, change the app lock or the sources, or use the laptop's microphone.
- Talking from the phone uses the phone's microphone; the laptop's Whisper turns it into text. Nothing goes to Apple or Google.
- The laptop must be awake. **Keep this laptop awake while remote access is on** (in the same card) stops it sleeping when idle, but closing the lid still suspends it.

## Updating

```bash
cd ~/SmartWardApp
git pull
python3 -m pip install --break-system-packages -r requirements.txt
scripts/build_ui.sh          # always
scripts/build_native.sh      # only if the window itself changed (frontend/src-tauri)
```

Then quit SmartWard from its tray icon and open it again. An open window shows an "updated, reload" bar; press it.

## Starting, stopping, and starting at login

- Closing the window keeps SmartWard running in the **tray**, so sources keep refreshing and indexing. The tray icon has **Open**, **Refresh**, **Index now**, **Lock now** and **Quit** (Quit stops the background service and the voice server too).
- **Settings → Desktop** can start SmartWard when you log in, hidden in the tray.
- From a terminal: `~/SmartWardApp/bin/start_smartward.sh` to start, `~/SmartWardApp/bin/start_smartward.sh stop` to stop.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| It locks while I'm using it | Settings → App lock: raise **Lock after no activity** (or choose Never) and **Lock after leaving the window**. Reading without touching anything still counts as idle after that time. |
| "Ollama isn't running" | Start it: `ollama serve` (or `sudo systemctl start ollama`). |
| Chat or summaries fail | `ollama pull llama3.2:3b`, then use the model test in Settings → Model. |
| Search finds only exact words | Install the embedding model: `ollama pull nomic-embed-text`. |
| Summaries and answers are slow | A CPU laptop takes time with long articles. Try the 3B model or a free OpenRouter model. |
| A source keeps failing | Open **Sources**; the failed source says why (blocked by robots.txt, not a feed, timeout). |
| "SmartWard's backend isn't running" | Quit from the tray icon and open it again. The log is `~/.local/state/smartward/api.log`. |
| No natural voice | Check Settings → Voice. Install it with `tts/setup.sh` and `sudo apt install libespeak-ng1 espeak-ng-data`. |
| Hands-free stays open for a long time | Usually the room: a fan or music that came on while you were quiet. It now lets go within a few seconds, but a very noisy room still confuses it; quiet the noise or move the microphone. |
| Hands-free says speech input isn't installed | Run `~/SmartWardApp/stt/setup.sh` and `sudo apt install alsa-utils`. |
| The phone can't connect | Is the laptop awake and SmartWard running? Tailscale connected on both? `tailscale serve status` should show 127.0.0.1:8000. |
| "This Tailscale account isn't allowed" | The login in Settings → Remote access must be the account your phone uses. |
| The tray icon is missing | GNOME needs its "AppIndicator" extension (on by default in Ubuntu). |

## Where things are

| | SmartWard |
| --- | --- |
| Program folder | `~/SmartWardApp` |
| Your library | `~/.local/share/smartward/smartward.db` |
| Log | `~/.local/state/smartward/api.log` |
| Address | `http://localhost:8000` (and `https://<laptop>.<tailnet>.ts.net` over Tailscale) |
| Menu entry | `~/.local/share/applications/com.mikefink.smartward.desktop` |

To remove SmartWard: quit it, delete `~/SmartWardApp`, delete the menu entry, and (only if you also want to delete your library) `~/.local/share/smartward`. Make an encrypted backup first if you might want it back.
