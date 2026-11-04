const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
(async () => {
  const { createStackController, createStackIndex, stackMembership, memberRoute } = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/pull-stacks.js"),
    ).href
  );
  const identity = { source: "https://github.com/octo/demo", reader: "gh:octo-reader" };
  const cached = {
    ...identity,
    state: "current",
    reason: null,
    fetched_at: "2026-09-17T12:00:00Z",
    fresh_for_s: 300,
    refreshing: false,
    last_refresh: null,
    complete: true,
    stacks: [
      { number: 286, base_ref: "main", open: true, pulls: [7, 8, 9] },
      { number: 900, base_ref: "topic", open: true, pulls: [9, 10] },
    ],
  };
  const index = createStackIndex(cached);
  assert.deepEqual(
    stackMembership(index, identity, 8).map((stack) => stack.number),
    [286],
  );
  assert.deepEqual(
    stackMembership(index, identity, 9).map((stack) => stack.number),
    [286, 900],
  );
  assert.deepEqual(stackMembership(index, { ...identity, reader: "gh:other" }, 8), []);
  assert.deepEqual(
    stackMembership(index, { ...identity, source: "https://github.com/octo/other" }, 8),
    [],
  );
  assert.deepEqual(stackMembership(index, null, 8), []);
  assert.deepEqual(memberRoute(9, "files"), {
    number: 9,
    tab: "files",
    reader: { fetchAfterMs: 0, initial: null },
  });
  let clock = Date.parse("2026-09-17T12:00:00Z");
  const timers = new Map();
  let nextTimer = 0;
  const calls = [];
  const pending = [];
  const controller = createStackController({
    request(method, route, options) {
      calls.push({ method, route, options });
      return new Promise((resolve) => pending.push(resolve));
    },
    now: () => clock,
    schedule(callback, delay) {
      const id = ++nextTimer;
      timers.set(id, { callback, delay });
      return id;
    },
    cancel(id) {
      timers.delete(id);
    },
    isVisible: () => true,
  });
  const seen = [];
  const first = controller.watch((value) => seen.push(value));
  const second = controller.watch(() => {});
  assert.equal(calls.length, 1, "two consumers share one read");
  const settle = async () => {
    for (let i = 0; i < 12; i += 1) {
      await Promise.resolve();
    }
  };
  pending.shift()({ status: 200, body: cached, etag: "v1" });
  await settle();
  assert.equal(calls.length, 1, "fresh cached stacks do not ask GitHub");
  assert.equal(seen.at(-1).byPull.get(8)[0].number, 286);
  const tick = async () => {
    const [id, timer] = timers.entries().next().value;
    timers.delete(id);
    timer.callback();
    await settle();
  };
  clock += 301000;
  await tick();
  pending.shift()({ status: 304, body: null, etag: "v1" });
  await settle();
  assert.equal(calls.at(-1).method, "POST");
  assert.equal(calls.at(-1).route, "/api/plugin/github/stacks-refresh");
  const failed = {
    ...cached,
    state: "stale",
    fresh_for_s: 0,
    last_refresh: {
      outcome: "network_error",
      message: "Offline",
      reset_at: null,
      at: new Date(clock).toISOString(),
    },
  };
  pending.shift()({ status: 200, body: { refresh: "not_due", stacks: failed }, etag: null });
  await settle();
  assert.equal(
    seen.at(-1).byPull.get(8)[0].number,
    286,
    "failed refresh preserves cached membership",
  );
  await tick();
  pending.shift()({ status: 200, body: failed, etag: "v3" });
  await settle();
  assert.equal(
    calls.filter((call) => call.method === "POST").length,
    1,
    "failure window prevents retry loops",
  );
  first.dispose();
  second.dispose();
  assert.equal(timers.size, 0);
  const reopened = controller.watch(() => {});
  const old = pending.shift();
  const oldSignal = calls.at(-1).options.signal;
  reopened.dispose();
  assert.equal(oldSignal.aborted, true);
  const again = controller.watch(() => {});
  assert.equal(calls.at(-1).method, "GET", "new owner reads without waiting for aborted request");
  pending.shift()({ status: 200, body: { ...cached, reader: "gh:new", stacks: [] }, etag: "new" });
  await settle();
  old({ status: 200, body: cached, etag: "old" });
  await settle();
  assert.equal(
    controller.snapshot().reader,
    "gh:new",
    "stale completion cannot overwrite new owner",
  );
  again.dispose();
  const beforeHidden = calls.length;
  const hidden = controller.watch(() => {}, false);
  assert.equal(calls.length, beforeHidden, "a hidden panel starts no optional read");
  hidden.setShown(true);
  pending.shift()({
    status: 200,
    etag: "missing",
    body: {
      ...cached,
      state: "absent",
      reason: "gh_stack_missing",
      reader: null,
      stacks: [],
      fresh_for_s: 300,
    },
  });
  await settle();
  assert.equal(
    calls.length,
    beforeHidden + 1,
    "unavailable optional tooling respects remaining backoff",
  );
  assert.equal(timers.size, 0, "missing optional tooling does not create a permanent poll loop");
  hidden.dispose();
  for (const failure of [
    new Error("the initial stack read failed"),
    { status: 503, body: null, etag: null },
    { status: 200, body: { malformed: true }, etag: null },
  ]) {
    const coldTimers = new Map();
    const coldCalls = [];
    const coldSeen = [];
    const cold = createStackController({
      request(method, route) {
        coldCalls.push({ method, route });
        if (coldCalls.length <= 2) {
          return failure instanceof Error ? Promise.reject(failure) : Promise.resolve(failure);
        }
        return Promise.resolve({ status: 200, body: cached, etag: "recovered" });
      },
      now: () => clock,
      schedule(callback, delay) {
        coldTimers.set(callback, delay);
        return callback;
      },
      cancel(timer) {
        coldTimers.delete(timer);
      },
      isVisible: () => true,
    });
    const reading = cold.watch((value) => coldSeen.push(value));
    await settle();
    assert.equal(cold.snapshot(), null);
    assert.equal(coldCalls.length, 1);
    assert.deepEqual([...coldTimers.values()], [30000], "initial failures retry at a bounded pace");
    reading.setShown(false);
    assert.equal(coldTimers.size, 0, "hiding cancels the cold retry");
    assert.equal(coldCalls.length, 1, "a hidden reader starts no retry");
    reading.setShown(true);
    await settle();
    assert.equal(coldCalls.length, 2, "showing resumes the cache read");
    assert.deepEqual([...coldTimers.values()], [30000]);
    const retry = coldTimers.keys().next().value;
    coldTimers.delete(retry);
    clock += 30000;
    retry();
    await settle();
    assert.equal(coldCalls.length, 3, "the scheduled retry recovers without another reader event");
    assert.ok(
      coldCalls.every(
        (call) => call.method === "GET" && call.route === "/api/plugin/github/stacks",
      ),
      "cold retries never start provider work",
    );
    assert.equal(coldSeen.at(-1).byPull.get(8)[0].number, 286);
    assert.deepEqual([...coldTimers.values()], [30000]);
    reading.dispose();
    assert.equal(coldTimers.size, 0, "disposal cancels the recovered poll");
  }
  const noRepository = controller.watch(() => {});
  pending.shift()({
    status: 200,
    etag: "not-github",
    body: { ...cached, state: "absent", reason: "not_github", reader: null, stacks: [] },
  });
  await settle();
  assert.equal(timers.size, 0, "a non-GitHub source does not poll optional stacks");
  noRepository.dispose();
  console.log(
    JSON.stringify({
      authoritativeMembership: true,
      multipleStacks: true,
      identityGuard: true,
      tabAndReaderIntent: true,
      sharedRead: true,
      failureRetention: true,
      retryWindow: true,
      disposal: true,
      lateOwnerGuard: true,
      initialFailureRetry: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
