use std::fs;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tauri::{Manager, WebviewWindow};

// ---------------------------------------------------------------------------
// Sidecar management
// ---------------------------------------------------------------------------

/// Holds the Python sidecar process and its discovered port.
struct Sidecar {
    process: Child,
    port: u16,
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        // Closing stdin signals the Python sidecar to shut down gracefully.
        // The sidecar's open_work_db context manager then stops Postgres.
        drop(self.process.stdin.take());
        let _ = self.process.wait();
    }
}

struct SidecarState(Mutex<Option<Sidecar>>);

/// Spawn the Python sidecar and wait for its readiness signal.
fn spawn_sidecar(work_dir: &str) -> Result<Sidecar, String> {
    // Prefer the project venv's Python; fall back to system python3.
    let python = find_python();

    let mut child = Command::new(&python)
        .args(["-m", "littera.desktop.server", "--work-dir", work_dir])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("Failed to spawn sidecar ({python}): {e}"))?;

    let stdout = child.stdout.take().ok_or("No stdout from sidecar")?;
    let reader = BufReader::new(stdout);

    for line in reader.lines() {
        let line = line.map_err(|e| format!("Failed to read sidecar stdout: {e}"))?;
        if let Some(port_str) = line.strip_prefix("LITTERA_SIDECAR_READY:") {
            let port: u16 = port_str
                .trim()
                .parse()
                .map_err(|e| format!("Invalid port from sidecar: {e}"))?;
            return Ok(Sidecar {
                process: child,
                port,
            });
        }
        // Forward other lines (e.g. PG startup messages) to stderr
        eprintln!("[sidecar] {line}");
    }

    Err("Sidecar exited before signaling readiness".to_string())
}

// ---------------------------------------------------------------------------
// Path helpers
// ---------------------------------------------------------------------------

/// Locate the project root (parent of `desktop/`).
fn project_root() -> PathBuf {
    // The Tauri binary/CWD lives inside desktop/src-tauri.
    // Walk up from CWD looking for pyproject.toml as anchor.
    let mut dir = std::env::current_dir().unwrap_or_else(|_| ".".into());
    for _ in 0..5 {
        if dir.join("pyproject.toml").exists() {
            return dir;
        }
        if !dir.pop() {
            break;
        }
    }
    // Fallback: assume CWD is desktop/, so parent is project root.
    std::env::current_dir()
        .map(|p| p.parent().unwrap_or(&p).to_path_buf())
        .unwrap_or_else(|_| ".".into())
}

/// Locate Python: prefer project .venv, then VIRTUAL_ENV, then system python3.
fn find_python() -> String {
    let root = project_root();

    // Check for a virtualenv at the project root
    let venv = root.join(".venv/bin/python");
    if venv.exists() {
        return venv.to_string_lossy().to_string();
    }

    // Check VIRTUAL_ENV env var
    if let Ok(venv_dir) = std::env::var("VIRTUAL_ENV") {
        let venv_python = Path::new(&venv_dir).join("bin/python");
        if venv_python.exists() {
            return venv_python.to_string_lossy().to_string();
        }
    }

    "python3".to_string()
}

/// Check whether a directory looks like a Littera work (has .littera/ subdir).
fn is_littera_work(path: &Path) -> bool {
    path.join(".littera").is_dir()
}

// ---------------------------------------------------------------------------
// Config persistence (~/.littera/desktop.json)
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize, Default, Clone)]
struct DesktopConfig {
    recent: Vec<RecentWork>,
    workspace: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
struct RecentWork {
    path: String,
    name: String,
    last_opened: u64,
}

fn config_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| ".".into())
        .join(".littera")
}

fn config_path() -> PathBuf {
    config_dir().join("desktop.json")
}

fn load_config() -> DesktopConfig {
    let path = config_path();
    match fs::read_to_string(&path) {
        Ok(contents) => serde_json::from_str(&contents).unwrap_or_default(),
        Err(_) => DesktopConfig::default(),
    }
}

fn save_config(config: &DesktopConfig) {
    let dir = config_dir();
    let _ = fs::create_dir_all(&dir);
    let path = config_path();
    if let Ok(json) = serde_json::to_string_pretty(config) {
        let _ = fs::write(path, json);
    }
}

fn now_epoch() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Add a work to the recent list (dedup by path, cap at 10).
fn record_recent(config: &mut DesktopConfig, path: &str) {
    let name = Path::new(path)
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| path.to_string());

    // Remove existing entry with same path
    config.recent.retain(|r| r.path != path);

    // Insert at front
    config.recent.insert(
        0,
        RecentWork {
            path: path.to_string(),
            name,
            last_opened: now_epoch(),
        },
    );

    // Cap at 10
    config.recent.truncate(10);
}

// ---------------------------------------------------------------------------
// Picker data structures
// ---------------------------------------------------------------------------

#[derive(Serialize, Clone)]
struct WorkEntry {
    name: String,
    path: String,
}

#[derive(Serialize)]
struct PickerData {
    recent: Vec<RecentWork>,
    workspace_works: Vec<WorkEntry>,
    workspace: Option<String>,
}

/// Scan immediate children of `dir` for Littera works.
fn scan_workspace(dir: &Path) -> Vec<WorkEntry> {
    let mut works = Vec::new();
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let child = entry.path();
            if child.is_dir() && is_littera_work(&child) {
                let name = child
                    .file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_default();
                works.push(WorkEntry {
                    name,
                    path: child.to_string_lossy().to_string(),
                });
            }
        }
    }
    works.sort_by(|a, b| a.name.cmp(&b.name));
    works
}

// ---------------------------------------------------------------------------
// IPC Commands
// ---------------------------------------------------------------------------

#[tauri::command]
fn sidecar_port(state: tauri::State<SidecarState>) -> Result<u16, String> {
    let guard = state.0.lock().map_err(|e| e.to_string())?;
    guard
        .as_ref()
        .map(|s| s.port)
        .ok_or_else(|| "Sidecar not ready".to_string())
}

#[tauri::command]
fn open_devtools(window: WebviewWindow) {
    window.open_devtools();
}

/// Load picker screen data: recent works + workspace contents.
#[tauri::command]
fn get_picker_data() -> PickerData {
    let config = load_config();
    let workspace_works = config
        .workspace
        .as_ref()
        .map(|ws| scan_workspace(Path::new(ws)))
        .unwrap_or_default();

    PickerData {
        recent: config.recent,
        workspace_works,
        workspace: config.workspace,
    }
}

/// Open native OS folder dialog via rfd.
#[tauri::command]
fn pick_folder() -> Option<String> {
    rfd::FileDialog::new()
        .pick_folder()
        .map(|p| p.to_string_lossy().to_string())
}

/// Set the workspace directory, save to config, return refreshed picker data.
#[tauri::command]
fn set_workspace(path: String) -> PickerData {
    let mut config = load_config();
    config.workspace = Some(path.clone());
    save_config(&config);

    let workspace_works = scan_workspace(Path::new(&path));
    PickerData {
        recent: config.recent,
        workspace_works,
        workspace: config.workspace,
    }
}

/// Validate that path is a Littera work, spawn sidecar, record in recents.
#[tauri::command]
fn open_work(path: String, state: tauri::State<SidecarState>) -> Result<u16, String> {
    let work_path = Path::new(&path);

    if !is_littera_work(work_path) {
        return Err(format!(
            "Not a Littera work (no .littera/ directory): {}",
            path
        ));
    }

    // Kill existing sidecar (drop replaces the old one)
    {
        let mut guard = state.0.lock().map_err(|e| e.to_string())?;
        *guard = None;
    }

    // Spawn new sidecar
    let sidecar = spawn_sidecar(&path)?;
    let port = sidecar.port;
    eprintln!("Sidecar ready on port {port} for {path}");

    {
        let mut guard = state.0.lock().map_err(|e| e.to_string())?;
        *guard = Some(sidecar);
    }

    // Record in recents
    let mut config = load_config();
    record_recent(&mut config, &path);
    save_config(&config);

    Ok(port)
}

/// Close the current work, stopping the sidecar.
#[tauri::command]
fn close_work(state: tauri::State<SidecarState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    *guard = None; // Drop triggers sidecar shutdown
    Ok(())
}

/// Initialize a new Littera work at the given path.
#[tauri::command]
fn init_work(path: String) -> Result<(), String> {
    let python = find_python();

    let output = Command::new(&python)
        .args(["-m", "littera", "init", &path])
        .output()
        .map_err(|e| format!("Failed to run littera init: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("littera init failed: {stderr}"));
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// App entry point
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            // Open devtools: invoke("open_devtools") from JS console,
            // or set LITTERA_DEVTOOLS=1 to auto-open on startup.
            #[cfg(debug_assertions)]
            if std::env::var("LITTERA_DEVTOOLS").is_ok() {
                if let Some(window) = app.get_webview_window("main") {
                    window.open_devtools();
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            sidecar_port,
            open_devtools,
            get_picker_data,
            pick_folder,
            set_workspace,
            open_work,
            close_work,
            init_work,
        ])
        .run(tauri::generate_context!())
        .expect("error running Littera");
}

fn main() {
    run();
}
