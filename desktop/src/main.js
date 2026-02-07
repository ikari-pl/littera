const { invoke } = window.__TAURI__.core;

async function init() {
  const status = document.getElementById("status");
  const list = document.getElementById("documents");

  try {
    const port = await invoke("sidecar_port");
    status.textContent = "Loading documents\u2026";

    const res = await fetch(`http://127.0.0.1:${port}/api/documents`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const docs = await res.json();

    if (docs.length === 0) {
      status.textContent = "No documents yet.";
      return;
    }

    status.style.display = "none";
    for (const doc of docs) {
      const li = document.createElement("li");
      li.textContent = doc.title || "(untitled)";
      li.dataset.id = doc.id;
      list.appendChild(li);
    }
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
    status.classList.add("error");
  }
}

init();
