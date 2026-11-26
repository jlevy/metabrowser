// Drive the same navigation used by the Guided Review tab, with a manually settled route.
const assert = require("node:assert/strict");
const { setImmediate: settle } = require("node:timers/promises");

async function main() {
  const { createGuideNavigation } = await import(
    "../../src/metabrowser/builtin_plugins/github/guided-review.js"
  );
  const calls = [];
  const states = [];
  const pending = [];
  /** The step count each render was told, which bounds the reader's moves. */
  const counts = [];
  const guide = createGuideNavigation({
    read(step, signal) {
      calls.push(step);
      return new Promise((resolve, reject) => pending.push({ signal, resolve, reject }));
    },
    render(answer, at, steps) {
      counts.push(steps);
      const shown = at === 0 ? "overview" : `step ${at}`;
      states.push(
        "step" in answer
          ? `${shown}: ${answer.state === "ready" ? "" : `${answer.state} `}step ${answer.step} of ${answer.step_count}`
          : `${shown}: ${answer.state}`,
      );
    },
  });
  function respond(result) {
    pending.shift().resolve(result);
    return settle();
  }
  function fail() {
    pending.shift().reject(new Error("offline"));
    return settle();
  }
  const titles = ["One", "Two", "Three"];
  /** @param {string} revision @param {number} step @param {Record<string, unknown>} [more] */
  const answer = (revision, step, more = {}) => ({
    state: "ready",
    record_revision: revision,
    step,
    step_count: titles.length,
    titles,
    references: [],
    ...more,
  });

  // A record with no revision is a preview: nothing is read, and nothing moves.
  guide.show(null, false);
  guide.move(1);
  assert.deepEqual(calls, []);

  // The guide opens on its overview, step 0, which shows the answer for step 1: its
  // titles list the guide. Before that answer the guide has no steps to move between.
  guide.show("first", false);
  guide.move(1);
  assert.deepEqual(calls, [1]);
  await respond(answer("first", 1));
  assert.equal(states.at(-1), "overview: step 1 of 3");
  guide.move(-1);
  assert.deepEqual(calls, [1]);

  // Step 1 is already in hand; step 2 is read; back to the overview and on to step 2
  // again reads nothing, since each answer is kept for its record revision.
  guide.move(1);
  assert.equal(states.at(-1), "step 1: step 1 of 3");
  guide.move(1);
  assert.equal(states.at(-1), "step 2: loading");
  await respond(answer("first", 2));
  guide.go(0);
  guide.go(2);
  assert.deepEqual(calls, [1, 2]);
  assert.equal(states.at(-1), "step 2: step 2 of 3");

  // A step from the list, and no move past the last one or before the first.
  guide.go(3);
  await respond(answer("first", 3));
  guide.move(1);
  guide.go(4);
  guide.go(-1);
  assert.deepEqual(calls, [1, 2, 3]);

  // GitHub reports a newer head: the kept answers are dropped and the step on screen is
  // asked for again, which the server answers as stale with the step still in it. A stale
  // guide's steps still move.
  guide.go(1);
  guide.show("first", true);
  assert.deepEqual(calls, [1, 2, 3, 1]);
  const stale = { stale: { changed_steps: [2] } };
  await respond(answer("first", 1, { state: "stale", ...stale }));
  assert.equal(states.at(-1), "step 1: stale step 1 of 3");
  guide.move(1);
  assert.equal(pending.length, 1);
  // A move while a read is on its way drops it for the newer one.
  guide.move(-1);
  assert.equal(pending[0].signal.aborted, true);
  assert.equal(states.at(-1), "step 1: stale step 1 of 3");
  pending.shift();
  guide.move(1);
  await respond(answer("first", 2, { state: "stale", ...stale }));
  assert.equal(states.at(-1), "step 2: stale step 2 of 3");

  // A new revision reads the step on screen again; a guide that lost that step falls back
  // to its first.
  guide.go(3);
  await respond(answer("first", 3, { state: "stale", ...stale }));
  guide.show("shorter", false);
  await respond({ state: "step_not_found", record_revision: "shorter" });
  await respond(answer("shorter", 1));
  assert.equal(states.at(-1), "step 1: step 1 of 3");

  // An answer for a revision other than the one asked for says the pull request updated.
  guide.show("third", false);
  await respond(answer("future", 1));
  assert.equal(states.at(-1), "step 1: updated");

  // A guide that cannot be read has no steps: its overview shows the refusal, and
  // nothing moves.
  guide.show("fourth", false);
  await respond({ state: "invalid", record_revision: "fourth" });
  const read = calls.length;
  guide.move(1);
  guide.go(0);
  assert.equal(calls.length, read);

  // A step whose read is refused or fails keeps the guide's steps, so the reader can still
  // move, and is read again when chosen again, the step on screen too; a step in hand is
  // not (B7 of review B on #677).
  guide.show("sixth", false);
  await respond(answer("sixth", 1));
  guide.go(2);
  await respond({ state: "comparison_unavailable", record_revision: "sixth" });
  assert.equal(states.at(-1), "step 2: comparison_unavailable");
  assert.equal(counts.at(-1), 3);
  guide.go(2);
  await fail();
  assert.equal(states.at(-1), "step 2: error");
  assert.equal(counts.at(-1), 3);
  guide.go(1);
  assert.equal(states.at(-1), "step 1: step 1 of 3");
  guide.go(1);
  guide.go(2);
  await respond(answer("sixth", 2));
  guide.go(2);
  assert.equal(states.at(-1), "step 2: step 2 of 3");
  assert.deepEqual(calls.slice(-4), [1, 2, 2, 2]);

  // An answer whose note, or its group's, a busy renderer or one that could not start
  // refused is not kept, so its step is read again when the reader returns to it and the
  // note renders once the renderer can; a note refused for its own sake, past the deadline,
  // keeps its answer, since the server would refuse it again at once.
  guide.show("seventh", false);
  await respond(answer("seventh", 2, { note_refusal: "renderer_busy" }));
  guide.go(1);
  await respond(answer("seventh", 1));
  guide.go(2);
  assert.equal(states.at(-1), "step 2: loading");
  await respond(answer("seventh", 2, { group_note_refusal: "renderer_unavailable" }));
  guide.go(1);
  guide.go(2);
  assert.equal(states.at(-1), "step 2: loading");
  await respond(answer("seventh", 2, { note_refusal: "render_deadline" }));
  guide.go(1);
  guide.go(2);
  assert.equal(states.at(-1), "step 2: step 2 of 3");
  assert.deepEqual(calls.slice(-4), [2, 1, 2, 2]);

  // Disposal drops the read on its way, and its late answer paints nothing.
  guide.show("fifth", false);
  const count = states.length;
  guide.dispose();
  assert.equal(pending[0].signal.aborted, true);
  await respond(answer("fifth", 1));
  assert.equal(states.length, count);

  // A stack's guide has no overview: it opens on step 1, which its first answer shows, and
  // no move goes before it.
  const stackCalls = [];
  const stackStates = [];
  const stack = createGuideNavigation({
    first: 1,
    read(step, signal) {
      stackCalls.push(step);
      return new Promise((resolve, reject) => pending.push({ signal, resolve, reject }));
    },
    render(answer, at) {
      stackStates.push(
        "step" in answer
          ? `step ${at}: step ${answer.step} of ${answer.step_count}`
          : `step ${at}: ${answer.state}`,
      );
    },
  });
  stack.show("stacked", false);
  await respond(answer("stacked", 1));
  assert.equal(stackStates.at(-1), "step 1: step 1 of 3");
  stack.move(-1);
  stack.go(0);
  assert.deepEqual(stackCalls, [1]);
  stack.move(1);
  await respond(answer("stacked", 2));
  stack.move(-1);
  stack.move(-1);
  assert.equal(stackStates.at(-1), "step 1: step 1 of 3");
  assert.deepEqual(stackCalls, [1, 2]);
  // A step read while the stack is pending, or cannot be paired, is refused before the guide
  // is found, so its answer names no revision: that is the step's refusal, never a new guide
  // (A1 of review A on #838). The guide keeps its steps, a step in hand is not read again,
  // and the refused step is read again when the reader returns to it.
  stack.go(3);
  await respond({ state: "not_cached", record_revision: null, stack: 70, carrier: null });
  assert.equal(stackStates.at(-1), "step 3: not_cached");
  stack.move(-1);
  assert.equal(stackStates.at(-1), "step 2: step 2 of 3");
  stack.move(1);
  await respond({ state: "stack_unavailable", record_revision: null, reason: "not_linear" });
  assert.equal(stackStates.at(-1), "step 3: stack_unavailable");
  stack.go(1);
  stack.go(3);
  await respond(answer("stacked", 3));
  assert.equal(stackStates.at(-1), "step 3: step 3 of 3");
  assert.deepEqual(stackCalls, [1, 2, 3, 3, 3]);
  stack.dispose();

  // The stack moves past the comparison its page draws, and the member that carries the
  // guide moves with it, whose author pins the guide again (B1 of review B on #838). Until
  // the reader takes the new comparison, an answer that names another revision is that
  // step's `stack_moved`, never a new guide, as is the route's own `stack_moved`: the steps
  // stay, and a step in hand is not read again. Shown the new revision then, the guide reads
  // nothing and says the same; once the comparison drawn is the stack's own, it is read.
  const movedCalls = [];
  const movedStates = [];
  const moved = createGuideNavigation({
    first: 1,
    read(step, signal) {
      movedCalls.push(step);
      return new Promise((resolve, reject) => pending.push({ signal, resolve, reject }));
    },
    render(answer, at, steps) {
      movedStates.push(
        "step" in answer
          ? `step ${at}: step ${answer.step} of ${answer.step_count}`
          : `step ${at}: ${answer.state}, ${steps} steps`,
      );
    },
  });
  moved.show("drawn", false);
  await respond(answer("drawn", 1));
  moved.behind("drawn");
  moved.move(1);
  await respond(answer("pinned again", 2));
  assert.equal(movedStates.at(-1), "step 2: stack_moved, 3 steps");
  moved.move(-1);
  assert.equal(movedStates.at(-1), "step 1: step 1 of 3");
  moved.go(3);
  await respond({ state: "stack_moved", record_revision: "pinned again", stack: 70, carrier: 10 });
  assert.equal(movedStates.at(-1), "step 3: stack_moved, 3 steps");
  // A move of another member leaves the carrier's revision: its steps read as before.
  moved.go(2);
  await respond(answer("drawn", 2));
  assert.equal(movedStates.at(-1), "step 2: step 2 of 3");
  const asked = movedCalls.length;
  moved.show("pinned again", false);
  assert.equal(
    movedCalls.length,
    asked,
    "a guide shown under a comparison it was not read at reads nothing",
  );
  assert.equal(movedStates.at(-1), "step 2: stack_moved, 0 steps");
  moved.behind(null);
  moved.show("pinned again", false);
  await respond(answer("pinned again", 2));
  assert.equal(movedStates.at(-1), "step 2: step 2 of 3");
  assert.deepEqual(movedCalls, [1, 2, 3, 2, 2]);
  moved.dispose();

  // Read ahead through the document's keep (guide-reads.js), as the page reads: once a step
  // is shown, the steps a move away are read, and a move to one shows it at once, with no
  // loading state and no read of its own. A guide mounted again over the same keep opens on
  // the step it kept and moves through what it kept, at once too, reading nothing; a new
  // revision shows none of what the old one kept.
  const { createGuideReads } = await import(
    "../../src/metabrowser/builtin_plugins/github/guide-reads.js"
  );
  const fetched = [];
  const flights = [];
  const keep = createGuideReads({
    fetch(url) {
      const step = Number(new URL(url, "http://localhost").searchParams.get("step"));
      fetched.push(step);
      return new Promise((resolve) => flights.push(resolve));
    },
  });
  async function deliver(body) {
    flights.shift()({ ok: true, text: async () => JSON.stringify(body) });
    for (let turn = 0; turn < 10; turn += 1) {
      await settle();
    }
  }
  const aheadStates = [];
  const mountAhead = (label) =>
    createGuideNavigation({
      read: (step, _signal, revision, moved) => keep.read("number=7", step, revision, moved),
      prefetch: (step, revision, moved) => keep.prefetch("number=7", step, revision, moved),
      peek: (step, revision, moved) => keep.peek("number=7", step, revision, moved),
      render(answer, at) {
        const shown = at === 0 ? "overview" : `step ${at}`;
        aheadStates.push(
          `${label} ${shown}: ${"step" in answer ? `step ${answer.step}` : answer.state} (read ${fetched.join(" ")})`,
        );
      },
    });
  const ahead = mountAhead("first mount");
  ahead.show("kept", false);
  await deliver(answer("kept", 1));
  assert.deepEqual(fetched, [1, 2], "the overview's step and the one after it");
  await deliver(answer("kept", 2));
  ahead.move(1);
  ahead.move(1);
  assert.equal(aheadStates.at(-1), "first mount step 2: step 2 (read 1 2)");
  assert.deepEqual(fetched, [1, 2, 3], "then the step after it");
  await deliver(answer("kept", 3));
  ahead.move(1);
  assert.equal(aheadStates.at(-1), "first mount step 3: step 3 (read 1 2 3)");
  ahead.dispose();
  const again = mountAhead("mounted again");
  again.show("kept", false);
  again.go(3);
  again.move(-1);
  assert.deepEqual(fetched, [1, 2, 3], "a guide mounted again reads nothing it kept");
  again.show("newer", false);
  assert.equal(aheadStates.at(-1), "mounted again step 2: loading (read 1 2 3)");
  assert.deepEqual(fetched, [1, 2, 3, 2], "the step the new revision shows is read again");
  await deliver(answer("newer", 2));
  again.dispose();
  assert.deepEqual(
    aheadStates.filter((state) => state.includes("loading")),
    ["first mount overview: loading (read )", "mounted again step 2: loading (read 1 2 3)"],
    "only a step no read has answered loads",
  );

  // What the keep holds is an answer for its record revision as the head stood when it was
  // read. GitHub can report a newer head with the record unchanged (`show`'s *moved*), and
  // the server then answers the guide's steps as out of date, so a guide shown that way
  // shows nothing the keep read before: it reads the step again, and keeps that answer for
  // the moved head. And an answer that cites another pull request this copy has not read is
  // never kept, so a reader who opens that one and comes back reads the step again, and
  // finds it filled in (review of #859, H1).
  const headRead = [];
  const headFlights = [];
  const headKeep = createGuideReads({
    fetch(url) {
      headRead.push(new URL(url, "http://localhost").searchParams.get("step"));
      return new Promise((resolve) => headFlights.push(resolve));
    },
  });
  async function deliverHead(body) {
    headFlights.shift()({ ok: true, text: async () => JSON.stringify(body) });
    for (let turn = 0; turn < 10; turn += 1) {
      await settle();
    }
  }
  const headStates = [];
  const mountHead = (label) =>
    createGuideNavigation({
      read: (step, _signal, revision, moved) => headKeep.read("number=8", step, revision, moved),
      prefetch: (step, revision, moved) => headKeep.prefetch("number=8", step, revision, moved),
      peek: (step, revision, moved) => headKeep.peek("number=8", step, revision, moved),
      render(answer, at) {
        const shown = at === 0 ? "overview" : `step ${at}`;
        const cites = "step" in answer ? answer.references.map((each) => each.state) : [];
        headStates.push(
          `${label} ${shown}: ${"step" in answer ? `${answer.state} step ${answer.step}` : answer.state}${cites.length > 0 ? `, citing ${cites.join(" ")}` : ""} (read ${headRead.join(" ")})`,
        );
      },
    });
  /** A one-step guide's answer, so nothing is read ahead. */
  const only = (revision, more = {}) => ({
    ...answer(revision, 1),
    step_count: 1,
    titles: ["One"],
    ...more,
  });
  const outOfDate = { state: "stale", stale: { github_newer: true, changed_steps: null } };
  const before = mountHead("before the push");
  before.show("same", false);
  await deliverHead(only("same"));
  before.dispose();
  const pushed = mountHead("after the push");
  pushed.show("same", false);
  assert.deepEqual(headRead, ["1"], "a guide mounted again over the keep reads nothing");
  pushed.show("same", true);
  assert.deepEqual(headRead, ["1", "1"], "the moved head reads the step again");
  await deliverHead(only("same", outOfDate));
  assert.equal(headStates.at(-1), "after the push overview: stale step 1 (read 1 1)");
  pushed.dispose();
  const movedAgain = mountHead("mounted again");
  movedAgain.show("same", true);
  assert.equal(headStates.at(-1), "mounted again overview: stale step 1 (read 1 1)");
  assert.deepEqual(headRead, ["1", "1"], "the answer for the moved head is kept for it");
  movedAgain.dispose();
  const elsewhere = { kind: "pull", pull: 9, path: null };
  const citing = mountHead("citing #9");
  citing.show("cites", false);
  await deliverHead(only("cites", { references: [{ ...elsewhere, state: "not_cached" }] }));
  citing.dispose();
  const opened = mountHead("#9 opened");
  opened.show("cites", false);
  assert.deepEqual(headRead, ["1", "1", "1", "1"], "a step citing what is not read is read again");
  await deliverHead(only("cites", { references: [{ ...elsewhere, state: "ready" }] }));
  opened.dispose();
  const back = mountHead("back again");
  back.show("cites", false);
  assert.deepEqual(headRead, ["1", "1", "1", "1"], "and kept once all it cites is read");
  back.dispose();
  console.log(
    JSON.stringify(
      {
        calls,
        states,
        stack: { calls: stackCalls, states: stackStates },
        moved: { calls: movedCalls, states: movedStates },
        ahead: { read: fetched, states: aheadStates },
        head: { read: headRead, states: headStates },
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
