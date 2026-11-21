// Agents built-in plugin: registers its views, whose code and stylesheets load on demand.
//
// Loading tier (docs/project/architecture/arch-browser-shell.md#asset-loading-tiers).
// The plugin offers views of the folder kind (the agents home and the session list), so
// the shell loads this file for every folder page, and a plugin's `styles.css` with it.
// This file is therefore a stub, and the plugin has no `styles.css`: every view's module
// and every rule are fetched the first time its view is shown.
//
//   folder      agents, agent-sessions  home.js, session-list.js      agents-views.css
//   agent-log   session                 session.js                     agents-views.css
//   agent-thread session, log           session.js                     agents-views.css
//   agent-log   log, charts, raw        agent-log.js (the renderers)   agent-log.css
//
// agents-views.css and agent-log.css (`--agent-kind-*` and `--agent-tool-*`, which the
// session page's event badges use too) are loaded by support.js.
//
// Measured on a plain folder page, as the files the shell fetches for it (2026-11-20,
// gzip -9, which is what the server's gzip middleware sends a client that accepts it):
//
//   before   index.js 18,699 bytes (6,132 gzipped) with the renderers in it, and
//            styles.css 10,485 (2,139): 29,184 bytes, 8,271 gzipped, on every folder page
//   after    index.js about 6.2 KB (2.3 KB gzipped; Chrome over loopback, uncompressed,
//            measured 6,175 bytes before this comment was last edited), the plugin's only
//            eager asset, most of it this comment; the renderers (agent-log.js, 17,777) and the stylesheet
//            (agent-log.css, 10,485) are fetched with a Log, Charts, Raw JSON, or Session
//            view and are in no folder page's load
//
// tests/dom/agents-views-chrome.mjs asserts in Chrome that a plain folder fetches this
// file and nothing else of the plugin, and prints the encoded bytes it measured.
//
// The agent-log views are registered here as stubs too, which load the renderers; once
// agent-log.js has run it registers the renderers over them.
//
// Exports ("Declared Dependencies" in docs/plugins.md): `loadLogRenderers`, which answers
// agent-log.js's exports, loading them and their stylesheet on demand. The unknown-jsonl
// and event-log plugins, which require this one, draw with them, and the shell's live tail
// appends events with its `renderLogEvent`. Loading this module stays as cheap as above.

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser agents plugin: window.metabrowser missing — SDK not loaded");
}

// Each view's module returns a handle with a disposer, which the view composition owns.
/**
 * @param {() => Promise<{render: (container: HTMLElement, ctx: any) => unknown}>} load
 */
function lazyView(load) {
  return {
    /** @param {HTMLElement} container @param {any} ctx */
    render: async (container, ctx) => {
      const view = await load();
      return view.render(container, ctx);
    },
  };
}
mb.registerView(
  "folder",
  "agents",
  lazyView(async () => (await import("./home.js")).createHomeView(mb)),
);
mb.registerView(
  "folder",
  "agent-sessions",
  lazyView(async () => (await import("./session-list.js")).createSessionListView(mb)),
);
const sessionPage = (/** @type {boolean} */ withHeader) =>
  lazyView(async () => (await import("./session.js")).createSessionView(mb, { withHeader }));
mb.registerView("agent-log", "session", sessionPage(true));
mb.registerView("agent-thread", "session", sessionPage(true));
mb.registerView("agent-thread", "log", sessionPage(false));

// The renderers and their stylesheet, loaded together once. A failed load is not kept,
// so the next view tries again.
/** @type {Promise<MetabrowserAgentLogRenderers> | null} */
let renderersLoading = null;
// The renderers once loaded, which a disposal reaches without waiting for them.
/** @type {MetabrowserAgentLogRenderers | null} */
let renderersLoaded = null;
// The renderers' specifier is a variable so that the strict type check, which follows a
// literal `import()` into the file, leaves the legacy-typed renderers where they are
// (tsconfig.json lists them as excluded); the browser resolves it as it does a literal.
const renderersModule = "./agent-log.js";
/** @returns {Promise<MetabrowserAgentLogRenderers>} */
function loadLogRenderers() {
  renderersLoading ??= Promise.all([
    import(renderersModule),
    import("./support.js").then((support) => support.ensureLogStyles()),
  ]).then(
    ([renderers]) => {
      renderersLoaded = renderers;
      return renderers;
    },
    (error) => {
      renderersLoading = null;
      throw error;
    },
  );
  return renderersLoading;
}

// A renderer of agent-log.js, named by its export. A pane replaced while the renderers
// load is not drawn into: `epochs` counts a container's renders and disposals, and only
// the latest render goes on.
/**
 * @param {"renderLog" | "renderCharts" | "renderRaw"} render
 * @param {"disposeLog" | "disposeCharts" | null} dispose
 */
function rendererView(render, dispose) {
  /** @type {WeakMap<HTMLElement, number>} */
  const epochs = new WeakMap();
  const next = (/** @type {HTMLElement} */ container) => {
    const epoch = (epochs.get(container) ?? 0) + 1;
    epochs.set(container, epoch);
    return epoch;
  };
  return {
    /** @param {HTMLElement} container @param {any} ctx */
    render: async (container, ctx) => {
      const epoch = next(container);
      const renderers = await loadLogRenderers();
      if (epochs.get(container) !== epoch) {
        return undefined;
      }
      return renderers[render](container, ctx);
    },
    /** @param {HTMLElement} container */
    dispose: (container) => {
      next(container);
      if (dispose && renderersLoaded) {
        renderersLoaded[dispose](container);
      }
    },
  };
}
mb.registerView("agent-log", "log", rendererView("renderLog", "disposeLog"));
mb.registerView("agent-log", "charts", rendererView("renderCharts", "disposeCharts"));
mb.registerView("agent-log", "raw", rendererView("renderRaw", null));

export { loadLogRenderers };
