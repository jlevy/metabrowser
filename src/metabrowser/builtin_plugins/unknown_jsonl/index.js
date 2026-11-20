// Generic JSONL draws with the agent-log plugin's renderers: the provider its manifest
// requires, whose exports it loads on demand ("Declared Dependencies" in docs/plugins.md).
(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser unknown-jsonl plugin: window.metabrowser missing — SDK not loaded");
    return;
  }

  /** @type {WeakMap<HTMLElement, object>} */
  const mounts = new WeakMap();
  /** @type {{disposeLog: (container?: HTMLElement) => void} | null} */
  let agentLog = null;

  /** @param {"renderLog" | "renderRaw"} renderer @returns {Parameters<typeof mb.registerView>[2]} */
  function sharedView(renderer) {
    return {
      async render(container, ctx) {
        const mount = {};
        mounts.set(container, mount);
        const provider = await mb.plugins.load("agent-log");
        agentLog = provider;
        if (mounts.get(container) !== mount) {
          return;
        }
        return provider[renderer](container, ctx);
      },
      dispose(container) {
        mounts.delete(container);
        // Raw JSON holds nothing to release; the log view's filters and listeners do.
        if (renderer === "renderLog") {
          agentLog?.disposeLog(container);
        }
      },
    };
  }

  mb.registerView("unknown-jsonl", "log", sharedView("renderLog"));
  mb.registerView("unknown-jsonl", "raw", sharedView("renderRaw"));
})();
