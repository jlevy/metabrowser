// Generic JSONL uses the agent-log renderers, loaded on demand through the SDK.
(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser unknown-jsonl plugin: window.metabrowser missing — SDK not loaded");
    return;
  }

  /** @type {WeakMap<HTMLElement, object>} */
  const mounts = new WeakMap();

  /** @param {"log" | "raw"} viewId @returns {Parameters<typeof mb.registerView>[2]} */
  function sharedView(viewId) {
    return {
      async render(container, ctx) {
        const mount = {};
        mounts.set(container, mount);
        await mb.ensureKindAssets("agent-log");
        if (mounts.get(container) !== mount) {
          return;
        }
        const view = mb.getRegisteredView("agent-log", viewId);
        if (!view) {
          throw new Error(`The JSONL ${viewId} renderer is unavailable.`);
        }
        return view.render(container, ctx);
      },
      dispose(container) {
        mounts.delete(container);
        mb.getRegisteredView("agent-log", viewId)?.dispose?.(container);
      },
    };
  }

  mb.registerView("unknown-jsonl", "log", sharedView("log"));
  mb.registerView("unknown-jsonl", "raw", sharedView("raw"));
})();
