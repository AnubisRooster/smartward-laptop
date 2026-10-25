//! SmartWard's desktop shell: one window, a tray icon, and a supervisor that keeps the
//! local API and the voice server running. The interface itself is the web app the API serves.

mod notify;
mod supervisor;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, RunEvent, WindowEvent};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

use supervisor::{post_api, Supervisor};

/// True when a tray icon was created. Without one, closing the window quits (nothing could reopen it).
struct TrayAvailable(Arc<AtomicBool>);

fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

#[tauri::command]
fn autostart_enabled(app: AppHandle) -> bool {
    app.autolaunch().is_enabled().unwrap_or(false)
}

#[tauri::command]
fn set_autostart(app: AppHandle, enabled: bool) -> Result<(), String> {
    let launcher = app.autolaunch();
    if enabled { launcher.enable() } else { launcher.disable() }.map_err(|e| e.to_string())
}

#[tauri::command]
fn quit_app(app: AppHandle) {
    app.exit(0);
}

fn build_tray(app: &tauri::App) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Open SmartWard", true, None::<&str>)?;
    let refresh = MenuItem::with_id(app, "refresh", "Refresh sources now", true, None::<&str>)?;
    let index = MenuItem::with_id(app, "index", "Index new articles now", true, None::<&str>)?;
    let clip = MenuItem::with_id(app, "clip", "Save link from clipboard", true, None::<&str>)?;
    let lock = MenuItem::with_id(app, "lock", "Lock now", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit SmartWard", true, None::<&str>)?;
    let menu = Menu::with_items(
        app,
        &[&open, &PredefinedMenuItem::separator(app)?, &clip, &refresh, &index, &lock, &PredefinedMenuItem::separator(app)?, &quit],
    )?;

    let mut builder = TrayIconBuilder::with_id("main")
        .tooltip("SmartWard")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_main(app),
            "refresh" => post_api("/api/refresh"),
            "index" => post_api("/api/pipeline/run"),
            "clip" => {
                show_main(app);
                let _ = app.emit("save-clipboard", ());
            }
            "lock" => {
                show_main(app);
                let _ = app.emit("lock-now", ());
            }
            "quit" => app.exit(0),
            _ => {}
        });
    // A white outline glyph: the top bar is dark, and the full-colour icon turns to mush at 22 px.
    match tauri::image::Image::from_bytes(include_bytes!("../icons/tray.png")) {
        Ok(glyph) => builder = builder.icon(glyph),
        Err(_) => {
            if let Some(icon) = app.default_window_icon() {
                builder = builder.icon(icon.clone());
            }
        }
    }
    builder.build(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Started at login: stay in the tray until you open it.
    let start_hidden = std::env::args().any(|a| a == "--hidden");

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_main(app)))
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, Some(vec!["--hidden"])))
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![autostart_enabled, set_autostart, quit_app])
        .setup(move |app| {
            let tray_ok = build_tray(app).map_err(|e| eprintln!("no tray icon: {e}")).is_ok();
            app.manage(TrayAvailable(Arc::new(AtomicBool::new(tray_ok))));
            app.manage(Supervisor::start(app.handle().clone()));
            notify::start(app.handle().clone());
            // Ctrl-C, `kill`, or the session ending: quit properly, so the API and voice server stop too.
            let handle = app.handle().clone();
            let _ = ctrlc::set_handler(move || handle.exit(0));
            if !start_hidden || !tray_ok {
                show_main(app.handle());
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let tray = window.app_handle().state::<TrayAvailable>();
                if tray.0.load(Ordering::Relaxed) {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building SmartWard");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            app.state::<Supervisor>().shutdown();
        }
    });
}
