// Event-log built-in plugin: Metabrowser's own structured event log, browsed.
//
// Owns four views of an `events-*.jsonl` file, each a query of the plugin's data hook
// (event_log_views.py) that the page draws (event-log-views.js):
//   ("event-log", "timeline") — spans nested under the spans that started them, in time order.
//   ("event-log", "latency")  — the slowest spans, and how all of them were distributed in time.
//   ("event-log", "kinds")    — each kind and name: how many, how they ended, how long they took.
//   ("event-log", "errors")   — failures by cause, the page's reports apart, unfinished work.
// The fifth, Raw JSON, is the agents plugin's JSONL renderer: the provider the manifest
// requires, whose exports load it on demand as the generic JSONL view loads it
// ("Declared Dependencies" in docs/plugins.md).

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

// Raw JSON holds nothing to release, so its dispose only forgets a mount still loading.
mb.registerView("event-log", "raw", {
  async render(container, ctx) {
    const mount = {};
    rawMounts.set(container, mount);
    const agentLog = await (await mb.plugins.load("agents")).loadLogRenderers();
    if (rawMounts.get(container) !== mount) {
      return;
    }
    return agentLog.renderRaw(container, ctx);
  },
  dispose(container) {
    rawMounts.delete(container);
  },
});
