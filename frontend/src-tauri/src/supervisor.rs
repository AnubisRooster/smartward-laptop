//! Keeps SmartWard's local API (and the natural-voice server) running while the app is open.
//!
//! - Starts `python3 smartward_api.py` if nothing answers on port 8000, and restarts it (with a
//!   growing pause) if it stops. An API that was already running is simply used.
//! - Starts the voice server through `tts/start.sh`; that script does nothing when it's running.
//! - Once the API answers, points the window at it: the interface is the web app the API serves,
//!   so a front-end change needs `scripts/build_ui.sh`, not a native rebuild.
//! - On quit, stops both, like `bin/start_smartward.sh stop`.

use std::fs::{self, File, OpenOptions};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager};

pub const API: &str = "http://127.0.0.1:8000";
const VOICE_HEALTH: &str = "http://127.0.0.1:8880/health";
const MAX_LOG_BYTES: u64 = 5 * 1024 * 1024;

struct Inner {
    app_dir: PathBuf,
    log_dir: PathBuf,
    quitting: AtomicBool,
    child: Mutex<Option<Child>>,
}

pub struct Supervisor(Arc<Inner>);

/// Where SmartWard's files live: `$SMARTWARD_HOME`, else two folders above the binary
/// (`<app>/resources/smartward-ui-bin/smartward`), else `~/SmartWardApp`.
fn find_app_dir() -> PathBuf {
    let valid = |p: &PathBuf| p.join("smartward_api.py").is_file();
    if let Ok(dir) = std::env::var("SMARTWARD_HOME") {
        let dir = PathBuf::from(dir);
        if valid(&dir) {
            return dir;
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent().and_then(|p| p.parent()).and_then(|p| p.parent()) {
            let dir = dir.to_path_buf();
            if valid(&dir) {
                return dir;
            }
        }
    }
    PathBuf::from(std::env::var("HOME").unwrap_or_default()).join("SmartWardApp")
}

fn log_dir() -> PathBuf {
    let base = std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".local/state"));
    base.join("smartward")
}

fn get_ok(url: &str, secs: u64) -> bool {
    ureq::get(url).timeout(Duration::from_secs(secs)).call().is_ok()
}

/// `/api/settings` only reads the database, so it answers even while a model is busy.
fn api_healthy() -> bool {
    get_ok(&format!("{API}/api/settings"), 3)
}

/// Fire-and-forget POST to the local API (tray menu actions).
pub fn post_api(path: &'static str) {
    thread::spawn(move || {
        let _ = ureq::post(&format!("{API}{path}"))
            .set("Content-Type", "application/json")
            .timeout(Duration::from_secs(10))
            .send_string("{}");
    });
}

impl Inner {
    fn open_log(&self) -> Option<File> {
        fs::create_dir_all(&self.log_dir).ok()?;
        let path = self.log_dir.join("api.log");
        if fs::metadata(&path).map(|m| m.len() > MAX_LOG_BYTES).unwrap_or(false) {
            let _ = fs::rename(&path, self.log_dir.join("api.log.1"));
        }
        OpenOptions::new().create(true).append(true).open(path).ok()
    }

    fn spawn_api(&self) -> std::io::Result<Child> {
        use std::os::unix::process::CommandExt;
        let mut cmd = Command::new("python3");
        cmd.arg(self.app_dir.join("smartward_api.py")).current_dir(&self.app_dir).stdin(Stdio::null());
        match self.open_log() {
            Some(log) => {
                cmd.stdout(log.try_clone()?).stderr(log);
            }
            None => {
                cmd.stdout(Stdio::null()).stderr(Stdio::null());
            }
        }
        // Its own process group: Ctrl-C in a terminal that launched the app doesn't kill it half-way.
        cmd.process_group(0).spawn()
    }

    fn start_voice(&self) {
        let script = self.app_dir.join("tts/start.sh");
        if script.is_file() {
            let _ = Command::new(script).current_dir(&self.app_dir).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).status();
        }
    }

    fn run(&self, app: AppHandle) {
        let mut failures: u32 = 0;
        let mut last_spawn = Instant::now() - Duration::from_secs(600);
        let mut last_voice_try = Instant::now() - Duration::from_secs(600);
        let mut shown_ui = false;

        while !self.quitting.load(Ordering::Relaxed) {
            if api_healthy() {
                failures = 0;
                if !shown_ui {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.eval(&format!("window.location.replace('{API}/')"));
                    }
                    shown_ui = true;
                }
                if last_voice_try.elapsed() > Duration::from_secs(30) {
                    last_voice_try = Instant::now();
                    if !get_ok(VOICE_HEALTH, 2) {
                        self.start_voice();
                    }
                }
            } else {
                shown_ui = false;
                let mut guard = self.child.lock().unwrap();
                let running = match guard.as_mut() {
                    Some(child) => matches!(child.try_wait(), Ok(None)),
                    None => false,
                };
                // A freshly started API needs a few seconds before it answers: don't pile up copies.
                let pause = Duration::from_secs((2u64 << failures.min(4)).min(30));
                if !running && last_spawn.elapsed() >= pause {
                    last_spawn = Instant::now();
                    failures += 1;
                    match self.spawn_api() {
                        Ok(child) => *guard = Some(child),
                        Err(e) => eprintln!("couldn't start the SmartWard API: {e}"),
                    }
                    last_voice_try = Instant::now() - Duration::from_secs(600);
                }
            }
            thread::sleep(Duration::from_secs(2));
        }
    }
}

impl Supervisor {
    pub fn start(app: AppHandle) -> Self {
        let inner = Arc::new(Inner {
            app_dir: find_app_dir(),
            log_dir: log_dir(),
            quitting: AtomicBool::new(false),
            child: Mutex::new(None),
        });
        let worker = inner.clone();
        thread::spawn(move || worker.run(app));
        Supervisor(inner)
    }

    /// Stops the API and the voice server, whoever started them.
    pub fn shutdown(&self) {
        self.0.quitting.store(true, Ordering::Relaxed);
        if let Some(mut child) = self.0.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        let script = self.0.app_dir.join("bin/start_smartward.sh");
        if script.is_file() {
            let _ = Command::new(script).arg("stop").current_dir(&self.0.app_dir).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).status();
        }
    }
}
