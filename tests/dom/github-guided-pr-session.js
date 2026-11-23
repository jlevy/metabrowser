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
    render(answer) {
      states.push(
        "step" in answer
          ? `${answer.state === "ready" ? "" : `${answer.state} `}step ${answer.step} of ${answer.step_count}`
          : answer.state,
      );
    },
  });
  function respond(result) {
    pending.shift().resolve(result);
    return settle();
  }

  guide.show(null, false);
  assert.deepEqual(calls, []);
  guide.show("first", false);
  await respond({ state: "ready", record_revision: "first", step: 1, step_count: 2 });
  guide.move(-1);
  assert.deepEqual(calls, [1]);

  guide.move(1);
  await respond({ state: "ready", record_revision: "first", step: 2, step_count: 2 });
  guide.move(1);
  guide.show("first", false);
  assert.deepEqual(calls, [1, 2]);

  guide.move(-1);
  assert.equal(pending[0].signal.aborted, false);
  // GitHub reports a newer head: the read on its way is dropped and the step is asked for
  // again, which the server answers as stale with the step still in it. A stale guide's steps
  // still move.
  guide.show("first", true);
  assert.equal(pending[0].signal.aborted, true);
  await respond({ state: "ready", record_revision: "first", step: 1, step_count: 2 });
  const stale = { state: "stale", record_revision: "first", step_count: 2, stale: {} };
  await respond({ ...stale, step: 1 });
  assert.equal(states.at(-1), "stale step 1 of 2");
  guide.move(1);
  await respond({ ...stale, step: 2 });
  assert.equal(states.at(-1), "stale step 2 of 2");

  guide.show("second", false);
  await respond({ state: "ready", record_revision: "second", step: 1, step_count: 2 });
  guide.move(1);
  await respond({ state: "ready", record_revision: "second", step: 2, step_count: 2 });
  guide.show("shorter", false);
  await respond({ state: "step_not_found", record_revision: "shorter" });
  await respond({ state: "ready", record_revision: "shorter", step: 1, step_count: 1 });

  guide.show("third", false);
  await respond({ state: "ready", record_revision: "future", step: 1, step_count: 1 });
  assert.equal(states.at(-1), "updated");

  guide.show("fourth", false);
  const count = states.length;
  guide.dispose();
  assert.equal(pending[0].signal.aborted, true);
  await respond({ state: "invalid", record_revision: "fourth" });
  assert.equal(states.length, count);
  console.log(JSON.stringify({ calls, states }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
