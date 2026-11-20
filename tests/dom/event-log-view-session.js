// Browserless session: Metabrowser's own event log browsed in Metabrowser, and what a page does with it.
//
// The event-log plugin (src/metabrowser/builtin_plugins/event_log/) draws an `events-*.jsonl`
// file as four views: Timeline, Latency, By kind, and Errors. The server counts, sorts, and
// nests (event_log_views.py); the page owns which filters are chosen, which rows are open,
// and which pages of the timeline it has read (event-log-model.js), and draws what the
// routes answer (event-log-views.js).
//
// This loads both production modules whole and drives them through a scripted page: a
// stand-in for the SDK (`fetchPluginData`, the filter controls, the toggle icon) and a DOM
// of just enough nodes to read the rows back. The answers are the server's, recorded in
// tests/fixtures/event-log-view-*-responses.json by tests/test_event_log_view_session.py, which
// fails when they drift; the request the page makes names the answer it gets, and a request
// the recording does not hold fails the session. The first page is the server's page of 20
// where its own is 200, so that the log has pages to read.
//
// Each step prints what the page shows after it, and the requests it made. Exits 1 on a
// failed invariant.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement } = require("./pulls-test-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const plugin = path.join(repoRoot, "src/metabrowser/builtin_plugins/event_log");
// The answers the server gave, in three recordings: each is under the fixtures' review budget.
const recording = { first_page: null, answers: {} };
for (const name of ["timeline", "latency", "summary"]) {
  const part = JSON.parse(
    fs.readFileSync(
      path.join(repoRoot, `tests/fixtures/event-log-view-${name}-responses.json`),
      "utf8",
    ),
  );
  Object.assign(recording.answers, part.answers);
  recording.first_page = part.first_page ?? recording.first_page;
}
const LOG = "events-20261119T220000Z-p7007-000.jsonl";

globalThis.document = {
  createElement: (tag) => new FakeElement(tag),
  body: new FakeElement("body"),
};

/** The request the page made, as the recording names it. */
function keyOf(route, params) {
  const all = { path: params.path, ...params };
  return `${route}?${new URLSearchParams(Object.entries(all).sort(([a], [b]) => (a < b ? -1 : 1)))}`;
}

const requests = [];
const unrecorded = [];
/** Each `fetchPluginData` the page makes: held until `release`, so the session can replace a view while one is out. */
let hold = null;

function createSdk() {
  const bound = new Map();
  const chips = new Map();
  const sdk = {
    formatInteger: (value) => String(value),
    icons: { toggle: "<svg data-icon='toggle'></svg>" },
    filterControls: {
      keepFocus: () => () => {},
      groupHtml: (spec) => {
        chips.set(spec.key, spec);
        return `<group ${spec.key}>`;
      },
      bind: (host, handlers) => {
        bound.set(host, handlers);
        return () => bound.delete(host);
      },
    },
    async fetchPluginData(pluginName, route, params, options) {
      assert.equal(pluginName, "event-log");
      const asked = { ...params };
      requests.push(keyOf(route, asked));
      // The first page is the server's page of 20, which the page cannot ask for itself.
      const isFirstPage = route === "timeline" && Object.keys(asked).length === 1;
      const key = isFirstPage ? recording.first_page : keyOf(route, asked);
      if (hold) {
        await hold.promise;
      }
      if (options?.signal?.aborted) {
        throw Object.assign(new Error("aborted"), { name: "AbortError" });
      }
      const answer = recording.answers[key];
      if (!answer) {
        unrecorded.push(key);
        throw new Error(`the recording has no answer for ${key}`);
      }
      if (answer.status !== 200) {
        throw Object.assign(new Error(`fetchPluginData ${route}: ${answer.status}`), {
          status: answer.status,
          payload: answer.body,
        });
      }
      return answer.body;
    },
  };
  return { sdk, bound, chips };
}

/** Let every answer the page is waiting for arrive and be drawn. */
async function settle() {
  for (let turn = 0; turn < 8; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** The notices a view puts above its rows, as the page says them. */
const headNotices = (container) =>
  container.childNodes[0].childNodes
    .filter((node) => node.classes?.has("event-log-notice"))
    .map((node) => `${node.dataset.severity ?? "neutral"}: ${node.textContent}`);

/** The rows the page drew, as one line each: where it sits, what it says, and how it ended. */
function outline(container) {
  const lines = [];
  const visit = (node) => {
    for (const child of node.childNodes) {
      if (!(child instanceof FakeElement)) {
        continue;
      }
      if (child.classes.has("event-log-head")) {
        continue;
      }
      if (child.classes.has("event-log-row")) {
        const head = child.childNodes[0];
        const [, kind, name, , when, took, outcome] = head.childNodes.map(
          (part) => part.textContent,
        );
        const depth = Number(child.style["--event-log-depth"]);
        const open = head.getAttribute("aria-expanded") === "true";
        lines.push(
          `${"  ".repeat(depth)}${open ? "v" : ">"} ${kind} ${name} ${when} ${took} ${outcome}`.trimEnd() +
            (child.dataset.context !== undefined ? " (context)" : ""),
        );
      } else if (child.classes.has("event-log-more")) {
        lines.push(
          `${"  ".repeat(Number(child.style["--event-log-depth"] ?? 0))}[${child.textContent}]`,
        );
      } else if (child.classes.has("event-log-notice")) {
        lines.push(`notice ${child.dataset.severity ?? "neutral"}: ${child.textContent}`);
      } else {
        visit(child);
      }
    }
  };
  visit(container);
  return lines;
}

/** The row for *key*'s header, to click. */
function rowFor(container, key) {
  let found = null;
  const visit = (node) => {
    for (const child of node.childNodes) {
      if (!(child instanceof FakeElement)) {
        continue;
      }
      if (child.classes.has("event-log-row") && child.dataset.key === key) {
        found = child;
      }
      visit(child);
    }
  };
  visit(container);
  assert(found, `no row ${key}`);
  return found;
}

const click = (element) => element.childNodes[0].listeners.get("click")();
const clickMore = (container) => {
  let more = null;
  const visit = (node) => {
    for (const child of node.childNodes) {
      if (child instanceof FakeElement) {
        if (child.classes.has("event-log-more") && !child.attributes.has("disabled")) {
          more = child;
        }
        visit(child);
      }
    }
  };
  visit(container);
  assert(more, "no Show more");
  more.listeners.get("click")();
};

const newContainer = () => {
  const container = new FakeElement("div");
  container.id = "pane";
  return container;
};

async function main() {
  const model = await import(pathToFileURL(path.join(plugin, "event-log-model.js")).href);
  const views = await import(pathToFileURL(path.join(plugin, "event-log-views.js")).href);
  const story = {};
  const taken = () => requests.splice(0, requests.length);
  const summaryOf = (container) =>
    container.childNodes[0].childNodes[0].childNodes.map((stat) =>
      stat.childNodes.map((part) => part.textContent).join(" "),
    );

  // ── The timeline: a first page of 20 of 44, and the offer of the rest ─────────────
  {
    const { sdk, bound, chips } = createSdk();
    const container = newContainer();
    views.mountEventLogView(container, { path: LOG }, sdk, "timeline");
    story["mounted, the answer not yet arrived"] = {
      body: container.childNodes[2].className,
      filters: container.childNodes[1].childNodes.length,
    };
    await settle();
    const first = outline(container);
    story["the timeline's first page"] = {
      requests: taken(),
      summary: summaryOf(container),
      notices: headNotices(container),
      filterGroups: [...chips.keys()],
      "kind chips": chips.get("event-log-kind").options.map((o) => o.value),
      "outcome chips": chips.get("event-log-outcome").options.map((o) => o.label),
      "minimum choices": chips.get("event-log-minimum").options.map((o) => o.label),
      rows: first.slice(0, 6),
      "rows shown": first.filter((line) => !line.startsWith("[") && !line.startsWith("notice"))
        .length,
      "the last line": first.at(-1),
    };

    // The next pages tile the first: each asks for the rows after those held, as long.
    clickMore(container);
    await settle();
    const second = outline(container);
    story["Show more reads the next page"] = {
      requests: taken(),
      "rows shown": second.filter((line) => !line.startsWith("[") && !line.startsWith("notice"))
        .length,
      "the last line": second.at(-1),
    };
    // A row with spans below opens to them, read when it opens and not again.
    click(rowFor(container, "7007:22"));
    await settle();
    story["a request opens to the job it started"] = {
      requests: taken(),
      around: outline(container).filter((line) => /pull-refresh|_pull_job/.test(line)),
    };
    click(rowFor(container, "7007:23"));
    await settle();
    story["and the job to the processes it ran"] = {
      requests: taken(),
      around: outline(container).filter((line) => /pull-refresh|_pull_job|gh api|probe/.test(line)),
    };
    click(rowFor(container, "7007:22"));
    story["closing the request hides everything under it"] = {
      requests: taken(),
      around: outline(container).filter((line) => /pull-refresh|_pull_job|gh api|probe/.test(line)),
    };
    click(rowFor(container, "7007:22"));
    story["opening it again reads nothing again"] = {
      requests: taken(),
      around: outline(container).filter((line) => /pull-refresh|_pull_job|gh api|probe/.test(line)),
    };

    // The detail a row opens to.
    click(rowFor(container, "7007:1"));
    const leaf = rowFor(container, "7007:1");
    story["a row with nothing below opens to its detail"] = {
      requests: taken(),
      expanded: leaf.childNodes[0].getAttribute("aria-expanded"),
      detail: leaf.childNodes[1]?.className,
      facts: leaf.childNodes[1]?.childNodes[0].textContent,
      attributes: leaf.childNodes[1]?.childNodes[1]?.textContent.replace(/\s+/g, " "),
    };
    click(leaf);

    clickMore(container);
    await settle();
    const third = outline(container);
    story["and the next, which ends the log"] = {
      requests: taken(),
      "rows shown": third.filter((line) => !line.startsWith("[") && !line.startsWith("notice"))
        .length,
      "the last line": third.at(-1),
    };

    // ── The filter bar ─────────────────────────────────────────────────────────────
    bound.get(container.childNodes[1]).onChange("event-log-kind", "job", "many");
    await settle();
    story["choosing the job kind asks again, with the filter"] = {
      requests: taken(),
      rows: outline(container),
      "chips drawn with": JSON.stringify(chips.get("event-log-kind").value),
    };
    click(rowFor(container, "7007:22"));
    await settle();
    story["a filtered request opens to the jobs, with the filter"] = {
      requests: taken(),
      rows: outline(container).slice(0, 4),
    };
    bound.get(container.childNodes[1]).onChange("event-log-outcome", "failed", "many");
    await settle();
    story["adding an outcome narrows it, and an open row is closed"] = {
      requests: taken(),
      rows: outline(container),
    };
    bound.get(container.childNodes[1]).onChange("event-log-outcome", "failed", "many");
    await settle();
    story["unchoosing the outcome keeps the kind"] = {
      requests: taken(),
      rows: outline(container).length,
    };
    bound.get(container.childNodes[1]).onChange("event-log-kind", "job", "many");
    await settle();
    story["and unchoosing the kind asks for the whole log again"] = {
      requests: taken(),
      rows: outline(container).length,
    };
  }

  // ── What the filter bar means ──────────────────────────────────────────────────
  {
    let filters = model.emptyFilters();
    filters = views.chosen(filters, "event-log-kind", "job");
    filters = views.chosen(filters, "event-log-kind", "request");
    filters = views.chosen(filters, "event-log-outcome", "timeout");
    filters = views.chosen(filters, "event-log-minimum", "2000");
    const asked = model.filterParams(filters);
    filters = views.chosen(filters, "event-log-kind", "job");
    filters = views.chosen(filters, "event-log-minimum", "");
    story["what a choice in the bar asks of the server"] = {
      chosen: asked,
      "after unchoosing job and the minimum": model.filterParams(filters),
      "another key": views.chosen(filters, "event-log-other", "x"),
      active: model.filtersActive(filters),
    };
  }

  // ── The other views ────────────────────────────────────────────────────────────
  {
    const { sdk, bound, chips } = createSdk();
    const container = newContainer();
    views.mountEventLogView(container, { path: LOG }, sdk, "latency");
    await settle();
    const latency = outline(container);
    story["Latency: the slowest, with their distribution"] = {
      requests: taken(),
      headings: container.childNodes[2].childNodes
        .filter((node) => node.localName === "h3")
        .map((node) => node.textContent),
      distribution: container.childNodes[2].childNodes[1].childNodes.map((column) =>
        column.childNodes.map((part) => part.textContent).join(" "),
      ),
      rows: latency.slice(0, 7),
    };
    click(rowFor(container, "7007:46"));
    story["a slow row opens to where it ran"] = {
      requests: taken(),
      path: rowFor(container, "7007:46").childNodes[1].textContent,
      facts: rowFor(container, "7007:46").childNodes[2].childNodes[0].textContent,
    };
    bound.get(container.childNodes[1]).onChange("event-log-kind", "subprocess", "many");
    await settle();
    story["Latency, filtered to processes"] = { requests: taken(), rows: outline(container) };
    assert.equal(chips.get("event-log-minimum").value, "");
  }
  {
    const { sdk, bound } = createSdk();
    const container = newContainer();
    views.mountEventLogView(container, { path: LOG }, sdk, "kinds");
    await settle();
    const body = container.childNodes[2];
    story["By kind: each kind and its names"] = {
      requests: taken(),
      sections: body.childNodes
        .filter((node) => node.localName === "section")
        .map((section) => ({
          heading: section.childNodes[0].textContent,
          outcomes: section.childNodes[1].textContent,
          names: section.childNodes[2].childNodes[1].childNodes.length,
        })),
      "the first table": section(body, 0).childNodes[2].childNodes[1].childNodes[0].childNodes.map(
        (cell) => cell.textContent,
      ),
    };
    bound.get(container.childNodes[1]).onChange("event-log-outcome", "failed", "many");
    await settle();
    story["By kind, of what failed"] = {
      requests: taken(),
      sections: container.childNodes[2].childNodes
        .filter((node) => node.localName === "section")
        .map((node) => node.childNodes[0].textContent),
    };
  }
  {
    const { sdk } = createSdk();
    const container = newContainer();
    views.mountEventLogView(container, { path: LOG }, sdk, "errors");
    await settle();
    const body = container.childNodes.at(-1);
    story["Errors: the causes first, the page's reports apart"] = {
      requests: taken(),
      "parts of the view": container.childNodes.map((part) => part.className),
      headings: body.childNodes
        .filter((node) => node.localName === "h3")
        .map((node) => node.textContent),
      causes: body.childNodes
        .filter((node) => node.className === "event-log-cause")
        .map((cause) =>
          cause.childNodes.map((part) =>
            part.localName === "ul"
              ? part.childNodes.map((item) => item.textContent)
              : part.textContent,
          ),
        ),
      unfinished: outline(container),
    };
  }

  // ── A refusal, and a view that outlives its answer ─────────────────────────────
  {
    const { sdk } = createSdk();
    const container = newContainer();
    views.mountEventLogView(container, { path: "absent.jsonl" }, sdk, "errors");
    await settle();
    story["a file the server refuses is said so, in an alert"] = {
      requests: taken(),
      body: outline(container),
    };
  }
  {
    const { sdk } = createSdk();
    const container = newContainer();
    let release;
    hold = { promise: new Promise((resolve) => (release = resolve)) };
    views.mountEventLogView(container, { path: LOG }, sdk, "kinds");
    views.mountEventLogView(container, { path: LOG }, sdk, "latency");
    views.disposeEventLogView(container);
    release();
    hold = null;
    await settle();
    story["a view replaced or disposed while its answer was out draws nothing"] = {
      requests: taken(),
      body: container.childNodes[2]?.className,
      rows: outline(container),
    };
  }

  // ── The model's own rules ──────────────────────────────────────────────────────
  story["a duration reads in the unit a person reads"] = Object.fromEntries(
    [0.04, 3.6, 41.2, 999, 2412.5, 15007.8, 32100, 125_000, 4_000_000].map((ms) => [
      String(ms),
      model.formatDuration(ms),
    ]),
  );
  story["the distribution's buckets are named from the server's edges"] = model.bucketLabels([
    1, 10, 100, 500, 2000, 10000,
  ]);
  story["a bar sits on the log's time axis and is never invisible"] = {
    "start of the log": model.axisBar({ start_ms: 0, elapsed_ms: 100 }, 1000, 0.003),
    "a hairline": model.axisBar({ start_ms: 500, elapsed_ms: 0.4 }, 230000, 0.003),
    "past the end": model.axisBar({ start_ms: 900, elapsed_ms: 500 }, 1000, 0.003),
    "no extent": model.axisBar({ start_ms: 0, elapsed_ms: 1 }, 0, 0.003),
    "a share of the longest": model.lengthShare(15, 60),
  };

  story["requests asked of the server"] = { unrecorded };
  process.stdout.write(`${JSON.stringify(story, null, 2)}\n`);
}

/** The i-th section of a By kind body. */
function section(body, index) {
  return body.childNodes.filter((node) => node.localName === "section")[index];
}

main().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
