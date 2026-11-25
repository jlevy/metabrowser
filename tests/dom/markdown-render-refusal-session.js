// Browserless session: a Markdown document whose render the server refused.
//
// Under the untrusted profile the server renders a document in its Markdown child under a
// deadline and answers one past it with a `kpress_render_refused` envelope
// (src/metabrowser/diff/markdown_projection_worker.py). This session runs the production
// Document view, mountRenderedMarkdown in builtin_plugins/markdown/rendered.js, and the
// folder Overview's README panel, createReadmePanel in builtin_plugins/folder/readme-panel.js,
// over the SDK's rejection for each refusal code, as fetchKpressRender makes it (an Error
// carrying the answer's status and payload), and records what each draws: one warning
// notice saying why, and the source in the render's place, from the window the page holds
// for a file it shows, or from the README's own window, read from /api/file, with a link to
// the file. A window that is not the whole file is said in the notice, with no Load more.
// A render that failed for another reason keeps the render-error box. Paint is the Chrome
// check's (tests/test_inert_render_refusal_chrome.py).

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2] || path.join(__dirname, "../.."));
const plugins = path.join(repoRoot, "src/metabrowser/builtin_plugins");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// The refusals the server answers, as `kpress_refusal_payload` builds them.
const REFUSALS = {
  render_deadline: {
    status: 422,
    payload: {
      type: "kpress_render_refused",
      code: "render_deadline",
      error: "Rendering took longer than 5 seconds, so it was stopped",
      deadline_ms: 5000,
      remembered: false,
      path: "slow.md",
    },
  },
  renderer_exited: {
    status: 422,
    payload: {
      type: "kpress_render_refused",
      code: "renderer_exited",
      error: "The renderer stopped while rendering this document",
      deadline_ms: 5000,
      remembered: true,
      path: "slow.md",
    },
  },
  renderer_unavailable: {
    status: 503,
    payload: {
      type: "kpress_render_refused",
      code: "renderer_unavailable",
      error: "The document renderer could not start",
      deadline_ms: 5000,
      remembered: false,
      path: "slow.md",
    },
  },
  renderer_busy: {
    status: 503,
    payload: {
      type: "kpress_render_refused",
      code: "renderer_busy",
      error: "The document renderer is busy with other documents",
      deadline_ms: 5000,
      remembered: false,
      path: "slow.md",
    },
  },
};
// A render KPress itself could not make: not a refusal, so the render error stays.
const FAILED = {
  status: 502,
  payload: {
    type: "kpress_render_error",
    error: "KPress render failed",
    detail: "boom",
    diagnostics: ["boom"],
  },
};

/** The SDK's rejection for a non-ok render answer (static/plugin-sdk.js). */
function rejection(answer) {
  const error = new Error(answer.payload.error);
  error.status = answer.status;
  error.payload = answer.payload;
  return error;
}

const escapeHtml = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

class ClassList {
  constructor(names = []) {
    this.names = new Set(names);
  }
  add(...names) {
    for (const name of names) {
      this.names.add(name);
    }
  }
  remove(...names) {
    for (const name of names) {
      this.names.delete(name);
    }
  }
  contains(name) {
    return this.names.has(name);
  }
}

// Enough of an element for the Document view and the refusal: classes, markup, and the
// one child the refusal looks up, the box its source is drawn in.
class Element {
  constructor(names = []) {
    this.classList = new ClassList(names);
    this.markup = "";
    this.sourceBox = null;
  }
  set innerHTML(value) {
    this.markup = value;
    this.sourceBox = value.includes('class="metabrowser-render-refused-source"')
      ? new Element()
      : null;
  }
  get innerHTML() {
    return this.markup;
  }
  querySelector(selector) {
    return selector === ".metabrowser-render-refused-source" ? this.sourceBox : null;
  }
}

function createSdk(answer, files) {
  const calls = { renders: [], completeText: [], fetched: [], sources: [] };
  const mb = {
    escapeHtml,
    errors: { isAbortError: (error) => error?.name === "AbortError" },
    formatSize: (bytes) => `${bytes} B`,
    navigation: { href: (target) => `/view/${target.path}` },
    perf: { measure: (_name, run) => run() },
    ensureKindAssets: async () => {},
    fetchCompleteText: async (ctx) => {
      calls.completeText.push(ctx.path);
      return files.complete;
    },
    fetchKpressRender: async (ctx, view, options) => {
      calls.renders.push({ path: ctx.path, view, includeToc: options.includeToc ?? null });
      throw rejection(answer);
    },
    renderSourceView: (container, data, options) => {
      calls.sources.push({
        path: data.path,
        ext: data.ext,
        content: data.content,
        continues: !!(data.content_truncated === true || typeof data.bytes_read === "number"),
        parts: (options?.parts || []).map((part) => part.language),
      });
      container.classList.add("metabrowser-source-host");
    },
  };
  globalThis.fetch = async (url) => {
    const asked = new URL(url);
    calls.fetched.push(`${asked.pathname}${asked.search}`);
    const envelope = files.envelopes[asked.searchParams.get("path")];
    return {
      ok: envelope !== undefined,
      status: envelope === undefined ? 404 : 200,
      json: async () => envelope,
    };
  };
  return { mb, calls };
}

// What a page holds for a Markdown file it shows: /api/file's first window.
const SLOW_TEXT = `---\ntitle: Slow\n---\n${"[".repeat(8)}${"%".repeat(24)}\n`;
const FILE_ENVELOPE = Object.freeze({
  type: "text",
  kind: "markdown",
  path: "slow.md",
  ext: ".md",
  size: SLOW_TEXT.length,
  content: SLOW_TEXT,
  content_bytes: SLOW_TEXT.length,
  bytes_read: SLOW_TEXT.length,
  content_truncated: false,
});
const WINDOW = "# Partial\n";
const PARTIAL_ENVELOPE = Object.freeze({
  ...FILE_ENVELOPE,
  size: 4096,
  content: WINDOW,
  content_bytes: WINDOW.length,
  bytes_read: WINDOW.length,
  content_truncated: true,
});
const README_TEXT = "# Readme\n\n[[[[%%%%\n";
const README_ENVELOPE = Object.freeze({
  type: "text",
  kind: "markdown",
  path: "README.md",
  ext: ".md",
  size: 9000,
  content: README_TEXT,
  content_bytes: README_TEXT.length,
  bytes_read: README_TEXT.length,
  content_truncated: true,
});

function drawn(container, calls) {
  return {
    classes: [...container.classList.names].sort(),
    markup: container.innerHTML,
    renderError: container.innerHTML.includes("metabrowser-kpress-render-error"),
    renders: calls.renders,
    completeText: calls.completeText,
    fetched: calls.fetched,
    sources: calls.sources,
  };
}

const NO_WORKER = Object.freeze({
  dispose() {},
  run: async () => ({ changed: false, complete: true, diagnostics: [], source: null }),
});

async function documentTab(rendered, answer, envelope, complete) {
  const { mb, calls } = createSdk(answer, { complete, envelopes: {} });
  const container = new Element(["content-body", "md-body"]);
  const handle = rendered.mountRenderedMarkdown(
    container,
    { path: envelope.path, raw: envelope },
    mb,
    { workerClient: NO_WORKER },
  );
  await handle.ready;
  handle.dispose();
  return drawn(container, calls);
}

(async () => {
  globalThis.location = { origin: "http://metabrowser.test" };
  globalThis.Worker = class {
    postMessage() {}
    terminate() {}
    addEventListener() {}
    removeEventListener() {}
  };
  // The panel's own source, which imports nothing: it hands the README to the Markdown
  // view, whose modules load from their files.
  const panelSource = fs.readFileSync(path.join(plugins, "folder/readme-panel.js"), "utf8");
  const [refusal, rendered, readme] = await Promise.all([
    import(pathToFileURL(path.join(plugins, "markdown/render-refusal.js")).href),
    import(pathToFileURL(path.join(plugins, "markdown/rendered.js")).href),
    import(`data:text/javascript;base64,${Buffer.from(panelSource).toString("base64")}`),
  ]);

  const recognized = {};
  const notes = {};
  for (const [code, answer] of Object.entries(REFUSALS)) {
    const found = refusal.renderRefusal(rejection(answer));
    recognized[code] = found;
    notes[code] = refusal.refusalNote(found);
  }
  recognized.kpress_render_error = refusal.renderRefusal(rejection(FAILED));
  recognized.abort = refusal.renderRefusal(Object.assign(new Error("x"), { name: "AbortError" }));
  notes.shortened = refusal.refusalNote({ code: "render_deadline", deadlineMs: 250 });

  const session = { recognized, notes };
  // The Document tab of a file the page shows: its own window, with no second read.
  session.documentTab = await documentTab(
    rendered,
    REFUSALS.render_deadline,
    FILE_ENVELOPE,
    SLOW_TEXT,
  );
  // A file longer than its first window: the view read it whole for the render, and shows
  // the window it holds, saying where the rest is.
  session.partialWindow = await documentTab(
    rendered,
    REFUSALS.render_deadline,
    PARTIAL_ENVELOPE,
    `${WINDOW}${"x".repeat(4096 - WINDOW.length)}`,
  );
  session.otherCodes = {};
  for (const code of ["renderer_exited", "renderer_unavailable", "renderer_busy"]) {
    const result = await documentTab(rendered, REFUSALS[code], FILE_ENVELOPE, SLOW_TEXT);
    session.otherCodes[code] = { markup: result.markup, renderError: result.renderError };
  }
  // A failed render's detail goes to the console, not the notice
  // (docs/design-system-messages.md): record that it did.
  const logged = [];
  const consoleError = console.error;
  console.error = (message, error) => logged.push(`${message} · ${error.message}`);
  let failed;
  try {
    failed = await documentTab(rendered, FAILED, FILE_ENVELOPE, SLOW_TEXT);
  } finally {
    console.error = consoleError;
  }
  session.renderFailure = {
    renderError: failed.renderError,
    sources: failed.sources,
    logged,
  };

  // The folder Overview's README panel: the README is not the page's file, so its window
  // is read from /api/file, and the notice links to the file for the rest.
  {
    const { mb, calls } = createSdk(REFUSALS.render_deadline, {
      complete: README_TEXT,
      envelopes: { "README.md": README_ENVELOPE },
    });
    mb.plugins = {
      load: async () => ({
        mountRendered: (container, ctx, options) =>
          rendered.mountRenderedMarkdown(container, ctx, mb, {
            ...options,
            workerClient: NO_WORKER,
          }),
      }),
    };
    const panel = readme.createReadmePanel(mb);
    const folder = { path: "", raw: { type: "folder", path: "", readme_path: "README.md" } };
    const resolved = panel.resolve(folder);
    const container = new Element(["folder-overview-panel-document"]);
    const handle = await panel.mount(container, folder, resolved.data, {});
    await handle.ready;
    handle.dispose();
    session.readmePanel = drawn(container, calls);
  }

  assert(session.documentTab.fetched.length === 0, "the file's own window is not read again");
  assert(!session.documentTab.renderError, "a refused document shows no render error");
  // The README keeps the table of contents its own page has (mb-kke3), so its render does
  // not turn the TOC off.
  assert(session.readmePanel.renders[0].includeToc !== "off", "the README keeps its TOC");
  assert(!session.readmePanel.renderError, "the README panel shows no render error");
  assert(session.renderFailure.renderError, "a failed render keeps its error");
  for (const result of [session.documentTab, session.partialWindow, session.readmePanel]) {
    assert(result.sources.length === 1, "one source view in the render's place");
    assert(!result.sources[0].continues, "the source offers no Load more of its own");
    assert(
      !result.classes.includes("metabrowser-kpress-host"),
      "a refused document is not set as a KPress document",
    );
  }
  console.log(JSON.stringify(session, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
