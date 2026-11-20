// Browserless session: what a page's file watches do once registered.
//
// static/file-watches.js keeps the paths a page watches on its event stream's connection
// (docs/project/architecture/arch-live-delivery.md, "File Watches").
// page-connections-session.js runs how a watch follows that connection across
// reconnects, restarts, and Back; this runs the rest, on the same page: the production
// app.js stream wiring, file-watches.js loaded as the asset loader loads it, and app.js's
// watchContainer and loadContainerChildren, extracted verbatim.
//
// - A watch released before its registration is answered is unregistered after it.
// - A watch refused for want of room registers again once another is released.
// - A hidden page's watches are unregistered, and registered again when it is shown.
// - A tree container's children follow its file: coalesced, one read at a time, drawn
//   only when they differ, read on expand when collapsed, and released with the row.
//
// Only the browser and the server are doubles. The server holds each connection's
// watched paths up to a bound and records them after each request, and can hold its
// answers as a slow server does; the document can be hidden and shown, and its
// MutationObserver reports that the tree changed when a step says so.

const { createPage, snapshotOf } = require("./page-connections-session.js");

/** A document that can be hidden and shown, with a tree MutationObserver can watch. */
function pageDocument(page) {
  const listeners = [];
  const observers = [];
  const doc = {
    visibilityState: "visible",
    addEventListener: (type, listener) => type === "visibilitychange" && listeners.push(listener),
    getElementById: (id) => (id === "tree-content" ? { id } : null),
  };
  page.sandbox.document = doc;
  page.sandbox.MutationObserver = class RecordingMutationObserver {
    constructor(callback) {
      this.callback = callback;
    }
    observe(target, options) {
      observers.push(this);
      page.note(`tree: observed #${target.id}${options.subtree ? " and its subtree" : ""}`);
    }
    disconnect() {
      observers.splice(observers.indexOf(this), 1);
      page.note("tree: no longer observed");
    }
  };
  return {
    /** Hide or show the page, as a browser's visibilitychange does. */
    visibility(state) {
      doc.visibilityState = state;
      for (const listener of listeners) {
        listener();
      }
    },
    /** The tree's rows changed, as a MutationObserver reports. */
    mutated() {
      for (const observer of [...observers]) {
        observer.callback([]);
      }
    },
  };
}

async function fileWatchesReleasedAndRetried() {
  const page = createPage("filesystem");
  const doc = pageDocument(page);
  page.server.maxPaths = 2;
  for (const file of ["a.csv", "b.csv", "c.csv", "d.csv"]) {
    page.server.generations.set(file, `${file[0]}1`);
  }
  await page.step("the page starts, and stream 1 sends the snapshot of connection c1", () => {
    page.start();
    page.opens(1);
    page.delivers(1, "fs.snapshot", snapshotOf(page, "c1"));
  });
  await page.step(
    "a table watches a.csv and leaves before the slow answer: unregistered after it",
    () => {
      const watches = page.loadFileWatches();
      page.server.holding = true;
      const dispose = watches.watch("a.csv", page.listener("a"), "a1");
      dispose();
      page.answerHeld();
    },
  );
  const disposers = {};
  await page.step("tables watch b.csv, c.csv, and d.csv: past the bound of 2, d is refused", () => {
    const watches = page.sandbox.MetabrowserFileWatches.shared();
    for (const file of ["b.csv", "c.csv", "d.csv"]) {
      disposers[file] = watches.watch(file, page.listener(file[0]), `${file[0]}1`);
    }
  });
  await page.step("b's table leaves: once b is unregistered, d registers again and is live", () =>
    disposers["b.csv"](),
  );
  await page.step("the page is hidden: every watch is unregistered, so none is polled", () =>
    doc.visibility("hidden"),
  );
  await page.step("d.csv changes while the page is hidden: nothing is told", () => {
    page.server.generations.set("d.csv", "d2");
  });
  await page.step(
    "the page is shown: each registers again with what it holds, and d hears d2 once",
    () => doc.visibility("visible"),
  );
  return {
    scenario: "a page's file watches are released, retried, and paused while hidden",
    steps: page.steps,
  };
}

/** A container's row in the tree and its children's group, as app.js draws them. */
function containerRow(page, file) {
  const attributes = new Map([["aria-expanded", "true"]]);
  let html = "";
  const row = {
    dataset: { path: file, containerPlugin: "sqlite", containerChildren: "children" },
    isConnected: true,
    getAttribute: (name) => attributes.get(name) ?? null,
    setAttribute: (name, value) => attributes.set(name, value),
  };
  const children = {
    dataset: {},
    get innerHTML() {
      return html;
    },
    set innerHTML(value) {
      html = value;
      page.note(
        `tree: ${file}'s children drawn: ${value.includes("tree-lazy-placeholder") ? "loading" : value}`,
      );
    },
  };
  return { row, children };
}

async function containerFollowsItsFile() {
  const page = createPage("filesystem");
  const doc = pageDocument(page);
  page.server.generations.set("app.db", "g1");
  page.server.children.set("app.db", ["users", "orders"]);
  await page.step("the page starts, and stream 1 sends the snapshot of connection c1", () => {
    page.start();
    page.opens(1);
    page.delivers(1, "fs.snapshot", snapshotOf(page, "c1"));
  });
  const { row, children } = containerRow(page, "app.db");
  page.sandbox.__container = { row, children };
  await page.step("app.db expanded: its children read and drawn, and its file followed", () =>
    page.run("void loadContainerChildren(__container.row, __container.children)"),
  );
  const changes = (...generations) => {
    for (const generation of generations) {
      page.server.generations.set("app.db", generation);
      page.delivers(1, "file.changed", { path: "app.db", generation });
    }
  };
  await page.step("its file changes three times in a burst: one read is due", () => {
    page.server.children.set("app.db", ["users", "orders", "items"]);
    changes("g2", "g3", "g4");
  });
  await page.step("the window ends: the children read once and drawn again", () =>
    page.elapse(300),
  );
  await page.step("a change that leaves the children as they were: read, not drawn", () => {
    changes("g5");
    page.elapse(300);
  });
  await page.step("a change while a slow read runs: it waits for that read", () => {
    page.server.holdingChildren = true;
    changes("g6");
    page.elapse(300);
    page.server.children.set("app.db", ["users", "items"]);
    changes("g7");
  });
  await page.step("the slow read answers and is drawn: one more read is due", () => {
    page.answerChildren();
  });
  await page.step("the next window ends: the children read again, unchanged since", () =>
    page.elapse(300),
  );
  await page.step(
    "app.db collapsed, then changed: its children are read on the next expand",
    () => {
      row.setAttribute("aria-expanded", "false");
      changes("g8");
      page.elapse(300);
      page.note(`tree: children loaded: ${children.dataset.loaded ?? "no"}`);
    },
  );
  await page.step(
    "the tree drops the row: its watch released, though the file is unchanged",
    () => {
      row.isConnected = false;
      doc.mutated();
    },
  );
  return { scenario: "a tree container's children follow its file", steps: page.steps };
}

async function main() {
  const transcript = [await fileWatchesReleasedAndRetried(), await containerFollowsItsFile()];
  console.log(JSON.stringify(transcript, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
