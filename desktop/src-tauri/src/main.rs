use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{Manager, WebviewWindow};

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

/// Locate the project root (parent of `desktop/`).
fn project_root() -> std::path::PathBuf {
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
        let venv_python = std::path::Path::new(&venv_dir).join("bin/python");
        if venv_python.exists() {
            return venv_python.to_string_lossy().to_string();
        }
    }

    "python3".to_string()
}

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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            let work_dir = std::env::var("LITTERA_WORK_DIR")
                .unwrap_or_else(|_| {
                    project_root().join("my-work").to_string_lossy().to_string()
                });

            let state = app.state::<SidecarState>();
            match spawn_sidecar(&work_dir) {
                Ok(sidecar) => {
                    eprintln!("Sidecar ready on port {}", sidecar.port);
                    *state.0.lock().unwrap() = Some(sidecar);
                }
                Err(e) => {
                    eprintln!("Failed to start sidecar: {e}");
                    // Let the app open anyway — frontend will show an error
                }
            }

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
        .invoke_handler(tauri::generate_handler![sidecar_port, open_devtools])
        .run(tauri::generate_context!())
        .expect("error running Littera");
}

fn main() {
    run();
}
