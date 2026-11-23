// Drive the same navigation used by the Guided PR tab, with a manually settled route.
const assert = require("node:assert/strict");
const { setImmediate: settle } = require("node:timers/promises");

async function main() {
  const { createGuideNavigation } = await import(
    "../../src/metabrowser/builtin_plugins/github/guided-pr.js"
  );
  const calls = [];
  const states = [];
  const pending = [];
  const guide = createGuideNavigation({
    read(step, signal) {
      calls.push(step);
      return new Promise((resolve) => pending.push({ signal, resolve }));
    },
    render(answer, at) {
      const shown = at === 0 ? "introduction" : `step ${at}`;
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
  const titles = ["One", "Two", "Three"];
  /** @param {string} revision @param {number} step @param {Record<string, unknown>} [more] */
  const answer = (revision, step, more = {}) => ({
    state: "ready",
    record_revision: revision,
    step,
    step_count: titles.length,
    titles,
    ...more,
  });

  // A record with no revision is a preview: nothing is read, and nothing moves.
  guide.show(null, false);
  guide.move(1);
  assert.deepEqual(calls, []);

  // The guide opens on its introduction, step 0, which shows the answer for step 1: its
  // titles list the guide. Before that answer the guide has no steps to move between.
  guide.show("first", false);
  guide.move(1);
  assert.deepEqual(calls, [1]);
  await respond(answer("first", 1));
  assert.equal(states.at(-1), "introduction: step 1 of 3");
  guide.move(-1);
  assert.deepEqual(calls, [1]);

  // Step 1 is already in hand; step 2 is read; back to the introduction and on to step 2
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

  // A guide that cannot be read has no steps: its introduction shows the refusal, and
  // nothing moves.
  guide.show("fourth", false);
  await respond({ state: "invalid", record_revision: "fourth" });
  const read = calls.length;
  guide.move(1);
  guide.go(0);
  assert.equal(calls.length, read);

  // Disposal drops the read on its way, and its late answer paints nothing.
  guide.show("fifth", false);
  const count = states.length;
  guide.dispose();
  assert.equal(pending[0].signal.aborted, true);
  await respond(answer("fifth", 1));
  assert.equal(states.length, count);
  console.log(JSON.stringify({ calls, states }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
