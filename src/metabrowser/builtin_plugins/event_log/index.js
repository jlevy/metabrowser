// Event-log built-in plugin: Metabrowser's own structured event log, browsed.
//
// Owns four views of an `events-*.jsonl` file, each a query of the plugin's data hook
// (event_log_views.py) that the page draws (event-log-views.js):
//   ("event-log", "timeline") — spans nested under the spans that started them, in time order.
//   ("event-log", "latency")  — the slowest spans, and how all of them were distributed in time.
//   ("event-log", "kinds")    — each kind and name: how many, how they ended, how long they took.
//   ("event-log", "errors")   — failures by cause, the page's reports apart, unfinished work.
// The fifth, Raw JSON, is the JSONL renderer's, loaded on demand through the SDK as the
// generic JSONL view loads it.

import { disposeEventLogView, mountEventLogView } from "./event-log-views.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser event-log plugin: SDK is unavailable");
}

/** @type {ReadonlyArray<"timeline" | "latency" | "kinds" | "errors">} */
const VIEWS = ["timeline", "latency", "kinds", "errors"];

for (const view of VIEWS) {
  mb.registerView("event-log", view, {
    render: (container, ctx) => mountEventLogView(container, ctx, mb, view),
    dispose: (container) => disposeEventLogView(container),
  });
}

/** @type {WeakMap<HTMLElement, object>} */
const rawMounts = new WeakMap();

mb.registerView("event-log", "raw", {
  async render(container, ctx) {
    const mount = {};
    rawMounts.set(container, mount);
    await mb.ensureKindAssets("agent-log");
    if (rawMounts.get(container) !== mount) {
      return;
    }
    const view = mb.getRegisteredView("agent-log", "raw");
    if (!view) {
      throw new Error("The JSONL raw renderer is unavailable.");
    }
    return view.render(container, ctx);
  },
  dispose(container) {
    rawMounts.delete(container);
    mb.getRegisteredView("agent-log", "raw")?.dispose?.(container);
  },
});
