// A closed or hidden file tree cannot publish replies into its next visible visit.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const root = path.resolve(__dirname, "../..");
const settle = async () => {
  for (let i = 0; i < 8; i += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
};
let nextGeneration = 0;
function envelope(file) {
  nextGeneration += 1;
  return {
    state: "current",
    reason: null,
    number: 7,
    listed_from: "github",
    source: "https://github.com/octo/demo",
    generation: nextGeneration.toString(16).padStart(32, "0"),
    fetched_at: "2026-09-17T12:00:00Z",
    reader: "gh:reader",
    head: "a".repeat(40),
    base: null,
    fresh_for_s: 60,
    refreshing: false,
    last_refresh: null,
    fetched: 1,
    pages: 1,
    last_page: 1,
    complete: true,
    capped: false,
    truncated: false,
    offset: 0,
    limit: 1,
    rows: [
      {
        path: file,
        display: file,
        previous_path: null,
        previous_display: null,
        status: "modified",
        additions: 1,
        deletions: 0,
      },
    ],
  };
}
function rig(create) {
  const requests = [];
  const timers = new Map();
  let model = null;
  let visible = true;
  const controller = create(
    {
      request(method, route, options) {
        return new Promise((resolve, reject) =>
          requests.push({ method, route, signal: options.signal, resolve, reject }),
        );
      },
      schedule(callback, delay) {
        const id = Symbol();
        timers.set(id, { callback, delay });
        return id;
      },
      cancel: (id) => timers.delete(id),
      now: () => 1000,
      isVisible: () => visible,
      formatTime: (stamp) => stamp,
      render: (next) => {
        model = next;
      },
      markAnchor() {},
      markCurrent() {},
      markMuted() {},
      page: () => null,
      open() {},
      leave() {},
    },
    { number: 7, autoExpandFiles: 100 },
  );
  const respond = (request, body) => request.resolve({ status: 200, etag: null, body });
  return {
    controller,
    requests,
    timers,
    respond,
    model: () => model,
    hide(mode) {
      if (mode === "collapse") {
        controller.collapse();
      } else if (mode === "panel") {
        controller.setShown(false);
      } else {
        visible = false;
        controller.onVisibilityChange();
      }
    },
    reopen(mode) {
      if (mode === "collapse") {
        controller.expand();
      } else if (mode === "panel") {
        controller.setShown(true);
      } else {
        visible = true;
        controller.onVisibilityChange();
      }
    },
  };
}
async function run() {
  const { createFileTreeController } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-files-tree.js")).href
  );
  let reads = 0;
  let refreshes = 0;
  for (const mode of ["collapse", "panel", "document"]) {
    for (const order of ["old-first", "new-first"]) {
      const r = rig(createFileTreeController);
      r.controller.expand();
      const old = r.requests[0];
      r.hide(mode);
      assert.equal(old.signal.aborted, true, `${mode} cancels its GET`);
      r.reopen(mode);
      assert.equal(r.requests.length, 2, `${mode} immediately owns a fresh GET`);
      const fresh = r.requests[1];
      if (order === "old-first") {
        r.respond(old, envelope("old.txt"));
        await settle();
        assert.equal(r.controller.snapshot().held, 0, "a late closed reply publishes nothing");
        r.controller.expand();
        assert.equal(r.requests.length, 2, "old finally did not release the active new GET");
      }
      r.respond(fresh, envelope("new.txt"));
      await settle();
      if (order === "new-first") {
        r.respond(old, envelope("old.txt"));
        await settle();
      }
      assert.deepEqual(
        r.model().rows.map((row) => row.id),
        ["new.txt"],
      );
      assert.equal(r.requests.filter((request) => request.method === "POST").length, 0);
      assert.deepEqual(
        [...r.timers.values()].map((timer) => timer.delay),
        [60000],
      );
      r.controller.dispose();
      reads += 1;
    }
    const abandonedReader = rig(createFileTreeController);
    abandonedReader.controller.expand();
    const oldReader = abandonedReader.requests[0];
    abandonedReader.hide(mode);
    abandonedReader.reopen(mode);
    abandonedReader.respond(abandonedReader.requests[1], {
      ...envelope(""),
      state: "absent",
      reason: "not_cached",
      listed_from: null,
      generation: null,
      fetched: 0,
      rows: [],
    });
    await settle();
    abandonedReader.respond(oldReader, envelope("old.txt"));
    await settle();
    assert.equal(
      abandonedReader.requests.filter((request) => request.method === "POST").length,
      1,
      "only the reopened cache miss may ask for a list",
    );
    abandonedReader.controller.dispose();
    reads += 1;
    const recent = rig(createFileTreeController);
    const missing = {
      ...envelope(""),
      state: "absent",
      reason: "not_cached",
      listed_from: null,
      generation: null,
      fetched: 0,
      rows: [],
    };
    recent.controller.expand();
    recent.respond(recent.requests[0], missing);
    await settle();
    const abandonedPost = recent.requests[1];
    assert.equal(abandonedPost.method, "POST");
    recent.hide(mode);
    recent.reopen(mode);
    recent.respond(recent.requests[2], missing);
    await settle();
    const waiting = recent.model();
    recent.respond(abandonedPost, { files: { ...missing, state: "pending", refreshing: true } });
    await settle();
    assert.deepEqual(recent.model(), waiting, "the old POST never owns the reopened visit");
    assert.equal(recent.model().loading, true);
    for (const body of [missing, envelope("ready.txt")]) {
      const [id, due] = [...recent.timers][0];
      assert.equal(due.delay, 1000, "a recent missing list keeps polling the local cache");
      recent.timers.delete(id);
      due.callback();
      const read = recent.requests.at(-1);
      assert.equal(read.method, "GET");
      recent.respond(read, body);
      await settle();
    }
    assert.equal(recent.requests.filter((request) => request.method === "POST").length, 1);
    assert.equal(recent.model().loading, false);
    assert.deepEqual(
      recent.model().rows.map((row) => row.id),
      ["ready.txt"],
    );
    assert.deepEqual(
      [...recent.timers.values()].map((timer) => timer.delay),
      [60000],
    );
    recent.controller.dispose();
    for (const failure of [false, true]) {
      const r = rig(createFileTreeController);
      r.controller.expand();
      const cached = envelope("before.txt");
      r.respond(r.requests[0], cached);
      await settle();
      const pending = r.controller.retry();
      const old = r.requests.at(-1);
      assert.equal(old.method, "POST");
      r.hide(mode);
      r.reopen(mode);
      const fresh = r.requests.at(-1);
      assert.equal(fresh.method, "GET", "reopened rows are read before old refresh completion");
      r.respond(fresh, { ...cached, offset: 1, rows: [] });
      await settle();
      const model = r.model();
      if (failure) {
        old.reject(Error("old refresh failed"));
      } else {
        r.respond(old, {
          files: { ...envelope("discarded.txt"), state: "pending", refreshing: true },
        });
      }
      await pending;
      await settle();
      assert.deepEqual(r.model(), model, "old POST cannot change the reopened envelope or error");
      assert.deepEqual(
        [...r.timers.values()].map((timer) => timer.delay),
        [60000],
      );
      r.controller.dispose();
      refreshes += 1;
    }
  }
  return { ownedReads: reads, ownedRefreshReplies: refreshes };
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
