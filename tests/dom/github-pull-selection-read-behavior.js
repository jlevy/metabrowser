// One selection reads a pull request's record once: the exact production Pulls controller
// opens the exact production page controller, which joins the read the row's peek started
// or takes the answer it just gave. Time, timers, and every answer are the session's, so a
// read can be held past the open's wait; only the reads of the record are counted here.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = path.resolve(__dirname, "../..");
const fixture = (name) =>
  JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures", name), "utf8"));
const lists = fixture("github-pulls-panel-responses.json");
const pages = fixture("github-pull-page-responses.json");
const list = structuredClone(lists.current);
list.body.rows = list.body.rows.map((row) => JSON.parse(row));
const current = pages.current.body;

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** A record answer for *number*, as the pull route gives one. */
function record(number) {
  return {
    status: 200,
    etag: `"record-${number}"`,
    verified: null,
    body: {
      ...current,
      number,
      record: { ...current.record, number, pull: { ...current.record.pull, number } },
    },
  };
}

async function story(panel, page, script) {
  let now = 0;
  const timers = new Map();
  let next = 1;
  const reads = [];
  const held = [];
  const pagesOpened = [];
  const schedule = (callback, delayMs) => {
    const handle = next;
    next += 1;
    timers.set(handle, { callback, at: now + delayMs });
    return handle;
  };
  const cancel = (handle) => timers.delete(handle);
  async function advance(target) {
    for (;;) {
      const due = [...timers.entries()]
        .filter(([, timer]) => timer.at <= target)
        .sort((a, b) => a[1].at - b[1].at)[0];
      if (due === undefined) {
        break;
      }
      timers.delete(due[0]);
      now = due[1].at;
      due[1].callback();
      await settle();
    }
    now = target;
  }
  /** A record read the session answers when it says, or at once for a revalidation. */
  function readRecord(who, route, options) {
    const number = Number(new URL(route, "http://localhost").searchParams.get("number"));
    const read = { who, at: now, etag: options.etag ?? null, number, aborted: false };
    reads.push(read);
    if (options.etag) {
      return Promise.resolve({ status: 304, etag: options.etag, body: null, verified: null });
    }
    return new Promise((resolve, reject) => {
      held.push({ resolve: () => resolve(record(number)) });
      options.signal?.addEventListener("abort", () => {
        read.aborted = true;
        reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
      });
    });
  }
  const controller = panel.createPullsController(
    {
      request(_method, route, options) {
        if (route.startsWith("/api/plugin/github/pull?")) {
          return readRecord("panel", route, options);
        }
        if (route.startsWith("/api/plugin/github/pulls?")) {
          return Promise.resolve({ status: 200, etag: list.etag, body: list.body });
        }
        // Background work the panel reads nothing back from.
        return new Promise(() => {});
      },
      schedule,
      cancel,
      now: () => now,
      isVisible: () => true,
      formatTime: (iso) => iso,
      render() {},
      markCurrent() {},
      markAnchor() {},
      reveal() {},
      open(route) {
        const opened = page.createPullController(
          {
            request(method, pageRoute, options) {
              if (method === "GET" && pageRoute.startsWith("/api/plugin/github/pull?")) {
                return readRecord("page", pageRoute, options);
              }
              return new Promise(() => {});
            },
            schedule,
            cancel,
            now: () => now,
            isVisible: () => true,
            render() {},
            renderMarkdown() {},
            reload() {},
            navigate() {},
          },
          { number: route.number, tab: route.tab, reader: route.reader },
        );
        // As the page host does, a page that another replaces is disposed.
        pagesOpened.at(-1)?.dispose();
        pagesOpened.push(opened);
        void opened.start();
      },
      filterChanged() {},
    },
    { filter: "all", current: null },
  );
  void controller.start({ shown: true });
  await settle();
  const answerRead = async () => {
    held.shift().resolve();
    await settle();
  };
  const result = await script({ controller, advance, answerRead, reads, pagesOpened, held });
  for (const opened of pagesOpened) {
    opened.dispose();
  }
  controller.dispose();
  return result;
}

async function run() {
  const panel = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pulls-panel.js")).href
  );
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const [first, second] = list.body.rows.map((row) => row.number);
  const facts = {};

  // A busy server: the mousedown's read is still on its way when the open stops waiting.
  facts.slowRead = await story(panel, page, async ({ controller, advance, answerRead, reads }) => {
    controller.focused(first);
    controller.peek(first);
    await advance(40);
    controller.activate(first);
    await advance(40 + panel.OPEN_WAIT_MS);
    assert.equal(reads.length, 1, "the page opened on the peek's read without one of its own");
    await answerRead();
    // The pointer rests on the row it clicked; the peek's hover timer fires after the open.
    controller.peek(first);
    await advance(40 + panel.OPEN_WAIT_MS + page.FAST_POLL_MS - 1);
    return reads.map((read) => read.who);
  });

  // The usual case: the read answered between mousedown and click.
  facts.fastRead = await story(panel, page, async ({ controller, advance, answerRead, reads }) => {
    controller.peek(first);
    await advance(20);
    await answerRead();
    await advance(60);
    controller.activate(first);
    await settle();
    controller.peek(first);
    await advance(60 + page.FAST_POLL_MS - 21);
    return reads.map((read) => read.who);
  });

  // A record read ahead long before the click is asked again, with its tag.
  facts.oldReadAhead = await story(
    panel,
    page,
    async ({ controller, advance, answerRead, reads }) => {
      controller.peek(second);
      await advance(20);
      await answerRead();
      await advance(5000);
      controller.activate(second);
      await settle();
      return reads.map((read) => `${read.who}${read.etag === null ? "" : " revalidates"}`);
    },
  );

  // Hovering another row while the joined read is on its way does not take it from the page.
  facts.hoverAway = await story(panel, page, async ({ controller, advance, answerRead, reads }) => {
    controller.peek(first);
    await advance(40);
    controller.activate(first);
    await advance(40 + panel.OPEN_WAIT_MS);
    controller.peek(second);
    await settle();
    await answerRead();
    await answerRead();
    await advance(40 + panel.OPEN_WAIT_MS + page.FAST_POLL_MS - 1);
    return reads.map((read) => read.who);
  });
  // A busy server answers nothing while the reader clicks four rows 300 ms apart: each read
  // handed to a page ends when the next row opens, and the last when its page goes.
  facts.superseded = await story(
    panel,
    page,
    async ({ controller, advance, reads, pagesOpened }) => {
      const rows = list.body.rows.slice(0, 4).map((row) => row.number);
      for (const [index, number] of rows.entries()) {
        await advance(index * 300);
        controller.peek(number);
        controller.activate(number);
        await advance(index * 300 + panel.OPEN_WAIT_MS + 1);
      }
      const inFlight = reads.filter((read) => !read.aborted).length;
      pagesOpened.at(-1).dispose();
      await settle();
      return {
        reads: reads.length,
        inFlight,
        afterLastPageWent: reads.filter((read) => !read.aborted).length,
      };
    },
  );
  return facts;
}

run()
  .then((result) => process.stdout.write(`${JSON.stringify(result, null, 2)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
