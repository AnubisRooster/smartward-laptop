//! Desktop notifications. Once a minute the shell asks the local API what is new (new relevant articles, a source that
//! started failing, a chat waiting for approval) and shows each as a normal desktop notification.

use std::process::Command;
use std::thread;
use std::time::Duration;
use tauri::AppHandle;

const POLL: &str = "http://127.0.0.1:8000/api/events/poll";

fn show(title: &str, body: &str) {
    // notify-send is on every GNOME desktop; if it is missing there is simply no notification.
    let _ = Command::new("notify-send").args(["--app-name=SmartWard", "--icon=smartward", "--expire-time=8000", title, body]).spawn();
}

pub fn start(app: AppHandle) {
    thread::spawn(move || {
        thread::sleep(Duration::from_secs(20));   // let the API come up and the first poll set the baseline
        loop {
            if let Ok(resp) = ureq::post(POLL).set("Content-Type", "application/json").timeout(Duration::from_secs(10)).send_string("{}") {
                if let Ok(text) = resp.into_string() {
                    if let Ok(v) = serde_json::from_str::<serde_json::Value>(&text) {
                        for e in v["events"].as_array().into_iter().flatten() {
                            show(e["title"].as_str().unwrap_or("SmartWard"), e["body"].as_str().unwrap_or(""));
                        }
                        if let Some(tray) = app.tray_by_id("main") {
                            let n = v["unread"].as_i64().unwrap_or(0);
                            let _ = tray.set_tooltip(Some(if n > 0 { format!("SmartWard · {n} unread") } else { "SmartWard".to_string() }));
                        }
                    }
                }
            }
            thread::sleep(Duration::from_secs(60));
        }
    });
}
