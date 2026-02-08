/**
 * fixtures.js — Mock data + setupPage() helper for Playwright tests.
 *
 * Mocks window.__TAURI__ to return picker data and handle IPC commands,
 * then intercepts all HTTP requests to the mock sidecar port with
 * pattern-matched mock responses.
 */

export const MOCK_PORT = 55555;
export const BASE = `http://127.0.0.1:${MOCK_PORT}`;
export const APP_URL = "http://localhost:5199";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

export const MOCK_DATA = {
  documents: [
    { id: "doc-1", title: "First Document" },
    { id: "doc-2", title: "Second Document" },
  ],

  sections: {
    "doc-1": [
      { id: "sec-1", title: "Introduction" },
      { id: "sec-2", title: "Methodology" },
    ],
    "doc-2": [
      { id: "sec-3", title: "Overview" },
    ],
  },

  blocks: {
    "sec-1": [
      {
        id: "blk-1",
        block_type: "prose",
        language: "en",
        source_text: "This is the first block of text.",
      },
      {
        id: "blk-2",
        block_type: "prose",
        language: "en",
        source_text: "Second block with a {@Concept|entity:ent-1} mention.",
      },
      {
        id: "blk-3",
        block_type: "prose",
        language: "pl",
        source_text: "Trzeci blok po polsku.",
      },
    ],
    "sec-2": [
      {
        id: "blk-4",
        block_type: "prose",
        language: "en",
        source_text: "Methodology content here.",
      },
    ],
  },

  entities: [
    { id: "ent-1", entity_type: "concept", label: "Concept" },
    { id: "ent-2", entity_type: "person", label: "Ada Lovelace" },
    { id: "ent-3", entity_type: "place", label: "Cambridge" },
  ],

  entityDetails: {
    "ent-1": {
      id: "ent-1",
      entity_type: "concept",
      label: "Concept",
      note: "A fundamental idea.",
      labels: [
        { language: "en", base_form: "Concept", aliases: "idea, notion" },
        { language: "pl", base_form: "Pojęcie", aliases: null },
      ],
      mentions: [
        {
          document: "First Document",
          section: "Introduction",
          language: "en",
          preview: "Second block with a Concept mention.",
        },
      ],
    },
    "ent-2": {
      id: "ent-2",
      entity_type: "person",
      label: "Ada Lovelace",
      note: "",
      labels: [
        { language: "en", base_form: "Ada Lovelace", aliases: null },
      ],
      mentions: [],
    },
    "ent-3": {
      id: "ent-3",
      entity_type: "place",
      label: "Cambridge",
      note: null,
      labels: [],
      mentions: [],
    },
  },

  pickerData: {
    recent: [
      { path: "/home/user/my-work", name: "my-work", last_opened: 1700000000 },
      { path: "/home/user/thesis", name: "thesis", last_opened: 1699000000 },
    ],
    workspace_works: [
      { path: "/home/user/workspace/project-a", name: "project-a" },
    ],
    workspace: "/home/user/workspace",
  },
};

// ---------------------------------------------------------------------------
// Route handler — pattern-matches URL → mock JSON
// ---------------------------------------------------------------------------

function routeHandler(route, request) {
  const url = new URL(request.url());
  const path = url.pathname;
  const method = request.method();

  // GET /api/documents
  if (method === "GET" && path === "/api/documents") {
    return route.fulfill({ json: MOCK_DATA.documents });
  }

  // GET /api/documents/:id/sections
  const secMatch = path.match(/^\/api\/documents\/([^/]+)\/sections$/);
  if (method === "GET" && secMatch) {
    const docId = secMatch[1];
    return route.fulfill({ json: MOCK_DATA.sections[docId] || [] });
  }

  // GET /api/sections/:id/blocks
  const blkMatch = path.match(/^\/api\/sections\/([^/]+)\/blocks$/);
  if (method === "GET" && blkMatch) {
    const secId = blkMatch[1];
    return route.fulfill({ json: MOCK_DATA.blocks[secId] || [] });
  }

  // GET /api/entities
  if (method === "GET" && path === "/api/entities") {
    return route.fulfill({ json: MOCK_DATA.entities });
  }

  // GET /api/entities/:id
  const entMatch = path.match(/^\/api\/entities\/([^/]+)$/);
  if (method === "GET" && entMatch) {
    const entId = entMatch[1];
    const detail = MOCK_DATA.entityDetails[entId];
    if (detail) return route.fulfill({ json: detail });
    return route.fulfill({ status: 404, json: { error: "Not found" } });
  }

  // GET /api/status
  if (method === "GET" && path === "/api/status") {
    return route.fulfill({ json: { status: "ok" } });
  }

  // POST /api/documents
  if (method === "POST" && path === "/api/documents") {
    return route.fulfill({
      json: { id: "doc-new", title: "New Document" },
    });
  }

  // POST /api/sections
  if (method === "POST" && path === "/api/sections") {
    return route.fulfill({
      json: { id: "sec-new", title: "New Section" },
    });
  }

  // POST /api/entities
  if (method === "POST" && path === "/api/entities") {
    return route.fulfill({
      json: { id: "ent-new", entity_type: "concept", label: "New Entity" },
    });
  }

  // POST /api/blocks
  if (method === "POST" && path === "/api/blocks") {
    return route.fulfill({
      json: { id: "blk-new", block_type: "prose", language: "en", source_text: "" },
    });
  }

  // PUT /api/blocks/batch
  if (method === "PUT" && path === "/api/blocks/batch") {
    return route.fulfill({ json: { success: true } });
  }

  // PUT /api/blocks/:id
  const blkPutMatch = path.match(/^\/api\/blocks\/([^/]+)$/);
  if (method === "PUT" && blkPutMatch) {
    return route.fulfill({ json: { success: true } });
  }

  // PUT /api/entities/:id/note
  const noteMatch = path.match(/^\/api\/entities\/([^/]+)\/note$/);
  if (method === "PUT" && noteMatch) {
    return route.fulfill({ json: { success: true } });
  }

  // DELETE /api/*
  if (method === "DELETE") {
    return route.fulfill({ json: { success: true } });
  }

  // Fallback
  return route.fulfill({ status: 404, json: { error: "Unknown route" } });
}

// ---------------------------------------------------------------------------
// setupPage — call before each test
// ---------------------------------------------------------------------------

/**
 * Sets up the page with Tauri mock and API route interception.
 * Must be called before page.goto().
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<typeof MOCK_DATA>} mock data for assertions
 */
export async function setupPage(page) {
  // Mock window.__TAURI__ before any page JS runs
  await page.addInitScript(`
    window.__TAURI__ = {
      core: {
        invoke: (cmd, args) => {
          if (cmd === "sidecar_port") return Promise.resolve(${MOCK_PORT});
          if (cmd === "get_picker_data") return Promise.resolve(${JSON.stringify(MOCK_DATA.pickerData)});
          if (cmd === "open_work") return Promise.resolve(${MOCK_PORT});
          if (cmd === "pick_folder") return Promise.resolve("/tmp/picked-folder");
          if (cmd === "set_workspace") return Promise.resolve(${JSON.stringify(MOCK_DATA.pickerData)});
          if (cmd === "init_work") return Promise.resolve(null);
          return Promise.reject("Unknown command: " + cmd);
        },
      },
    };
  `);

  // Intercept all API calls to the mock sidecar port
  await page.route(`${BASE}/api/**`, routeHandler);

  return MOCK_DATA;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Navigate to app and wait for picker, then click first recent work
 * to transition through to the main UI with sidebar.
 */
export async function gotoApp(page) {
  await page.goto(APP_URL);
  // Wait for picker to render with recent works
  await page.locator(".picker-work-item").first().waitFor({ state: "visible", timeout: 5000 });
  // Click the first recent work to open it
  await page.locator(".picker-work-item").first().click();
  // Wait for sidebar to populate with documents
  await page.locator(".sidebar-item").first().waitFor({ state: "visible", timeout: 5000 });
}

/**
 * Navigate into a document (click first doc in sidebar).
 */
export async function navToDocument(page) {
  await page.locator(".sidebar-item").first().click();
  await page.locator(".sidebar-item").first().waitFor({ state: "visible", timeout: 5000 });
}

/**
 * Navigate into a section (click first section in sidebar).
 * Returns once the editor is visible.
 */
export async function navToSection(page) {
  await page.locator(".sidebar-item").first().click();
  await page.locator("#prosemirror-editor .ProseMirror").waitFor({ state: "visible", timeout: 5000 });
}

/**
 * Full navigation: app → first doc → first section → editor ready.
 */
export async function navToEditor(page) {
  await gotoApp(page);
  await navToDocument(page);
  await navToSection(page);
}
