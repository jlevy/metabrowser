// Drive the same paged node table that the standalone file view mounts.
const assert = require("node:assert/strict");
const { FakeElement } = require("./pulls-test-dom.js");

const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...args) => {
  if (!String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    emitWarning.call(process, warning, ...args);
  }
};

async function main() {
  const { mountNodeTable } = await import("../../src/metabrowser/static/structured-node-table.js");
  global.document = {
    createElement: (tag) => new FakeElement(tag),
    createComment: () => new FakeElement("#comment"),
  };
  const scalar = (value, kind = typeof value) => ({ kind, value, child_count: 0 });
  const array = (children, child_count = children.length) => ({
    kind: "array",
    child_count,
    children: children.map((node, segment) => ({ segment, node })),
  });
  const object = (children, child_count = children.length) => ({
    kind: "object",
    child_count,
    children: children.map(([segment, node]) => ({ segment, node })),
  });
  const summaries = [];
  function visibleText(node) {
    if (node.hidden) {
      return "";
    }
    return node.childNodes?.length ? node.childNodes.map(visibleText).join("") : node.textContent;
  }
  for (const [node, expected, total] of [
    [array([scalar("host"), scalar("editor")]), '["host", "editor"]', "2 items"],
    [
      object([
        ["a", scalar(1)],
        ["b", array([scalar(true), scalar(null, "null")])],
      ]),
      '{"a": 1, "b": [true, null]}',
      "2 keys",
    ],
    [object([['quote"', scalar("line\nnext")]]), '{"quote\\"": "line\\nnext"}', "1 key"],
    [array([scalar("9007199254740993", "number")]), "[9007199254740993]", "1 item"],
    [array([scalar(1)], 12), "[1, …] (12 items)", "12 items"],
    [object([], 2), "{…} (2 keys)", "2 keys"],
  ]) {
    const previewHost = document.createElement("div");
    const preview = mountNodeTable(previewHost, async () => ({
      status: "ready",
      node: object([], 1),
      children: [{ segment: "value", node }],
    }));
    await preview.ready;
    const toggle = previewHost.lastChild.firstChild.lastChild.firstChild.childNodes[1].firstChild;
    assert.equal(visibleText(toggle), expected);
    assert.equal(toggle.getAttribute("aria-label"), `${toggle.firstChild.textContent} (${total})`);
    assert.ok(toggle.dataset.tipText.includes(total));
    assert.equal(toggle.lastChild.getAttribute("aria-hidden"), "true");
    summaries.push(expected);
    preview.dispose();
  }
  const boundedHost = document.createElement("div");
  const bounded = mountNodeTable(boundedHost, async () => ({
    status: "ready",
    node: object([], 1),
    children: [{ segment: "value", node: array([scalar("x".repeat(10_000))], 100) }],
  }));
  await bounded.ready;
  const boundedToggle =
    boundedHost.lastChild.firstChild.lastChild.firstChild.childNodes[1].firstChild;
  assert.ok(boundedToggle.textContent.startsWith('["'));
  assert.ok(boundedToggle.textContent.includes("…"));
  assert.ok(boundedToggle.textContent.endsWith("(100 items)"));
  assert.ok(boundedToggle.textContent.length < 120);
  bounded.dispose();

  const previewHost = document.createElement("div");
  const partialMap = {
    ...object([["first", scalar("a".repeat(55) + "🙂".repeat(60))]]),
    partial: true,
  };
  const positionsOpened = [];
  const preview = mountNodeTable(
    previewHost,
    async () => ({
      status: "ready",
      preview: true,
      node: { ...object([], 1), partial: true },
      children: [{ segment: "entries", node: partialMap }],
    }),
    {
      openSource: (position) => positionsOpened.push(position),
      copyRow: async () => "example",
    },
  );
  await preview.ready;
  const notice = previewHost.lastChild.firstChild.firstChild;
  assert.ok(notice.textContent.includes("first complete YAML values"));
  notice.lastChild.listeners.get("click")();
  assert.deepEqual(positionsOpened, [{ document: 0, path: [], offset: 0 }]);
  const previewRows = previewHost.lastChild.lastChild.lastChild.childNodes;
  const parent = previewRows[0];
  assert.ok(parent.childNodes[1].textContent.includes("at least 1 key"));
  assert.ok(!/\\ud[89ab][0-9a-f]{2}/i.test(parent.childNodes[1].textContent));
  assert.equal(parent.childNodes[2].childNodes.length, 0);
  assert.equal(previewRows[1].childNodes[2].firstChild.getAttribute("aria-label"), "Copy first");
  preview.dispose();

  const observed = [];
  document.defaultView = {
    ResizeObserver: class {
      constructor(callback) {
        this.callback = callback;
        observed.push(this);
      }
      observe(target) {
        this.target = target;
      }
      disconnect() {
        this.disconnected = true;
      }
    },
  };
  const resizeHost = document.createElement("div");
  const resizing = mountNodeTable(resizeHost, async () => ({
    status: "ready",
    node: object([], 1),
    children: [{ segment: "value", node: array([array([scalar("host")])]) }],
  }));
  await resizing.ready;
  assert.equal(observed.length, 1);
  assert.equal(observed[0].target, resizeHost);
  const rows = resizeHost.lastChild.firstChild.lastChild;
  const resizeToggle = rows.firstChild.childNodes[1].firstChild;
  const previewText = resizeToggle.firstChild;
  const previewCount = resizeToggle.childNodes[1];
  assert.equal(previewCount.hidden, true);
  previewText.scrollWidth = 140;
  previewText.clientWidth = 50;
  observed[0].callback();
  await new Promise(setImmediate);
  assert.equal(previewCount.hidden, false);
  assert.ok(visibleText(resizeToggle).endsWith("(1 item)"));
  previewText.clientWidth = 180;
  observed[0].callback();
  await new Promise(setImmediate);
  assert.equal(previewCount.hidden, true);
  const detachedPreview = rows.childNodes[1].childNodes[1].firstChild.firstChild;
  Object.defineProperty(detachedPreview, "clientWidth", {
    get() {
      assert.fail("A collapsed branch must leave the measured previews");
    },
  });
  resizeToggle.listeners.get("click")();
  await new Promise(setImmediate);
  resizing.dispose();
  assert.equal(observed[0].disconnected, true);
  Object.defineProperty(previewText, "clientWidth", {
    get() {
      assert.fail("A disposed table must not measure its old rows");
    },
  });
  observed[0].callback();
  await new Promise(setImmediate);
  delete document.defaultView;
  const host = document.createElement("div");
  const root = { kind: "object", child_count: 2 };
  const list = { kind: "array", child_count: 1 };
  const mapping = { kind: "object", child_count: 2 };
  const number = { kind: "number", value: "9007199254740993" };
  const positions = [];
  const selections = [];
  let finish;
  const mounted = mountNodeTable(
    host,
    ({ path, offset }, signal, depth) => {
      positions.push({ path, offset, depth });
      if (path.length) {
        assert.deepEqual(path, ["0", 0, "record"]);
        return {
          status: "ready",
          node: mapping,
          children: [{ segment: offset ? "last" : "id", node: number }],
          next_offset: offset ? null : 1,
        };
      }
      if (offset) {
        return new Promise((resolve) => {
          finish = () => {
            assert.equal(signal.aborted, true);
            resolve({ status: "ready", node: { kind: "string", value: "obsolete" } });
          };
        });
      }
      const preview = {
        kind: "object",
        child_count: 1,
        children: [{ segment: "record", node: mapping }],
      };
      const array = { ...list, children: [{ segment: 0, node: preview }] };
      return {
        status: "ready",
        node: root,
        children: [
          { segment: "0", node: array },
          { segment: "keep", node: { kind: "string", value: "sibling" } },
        ],
        next_offset: 1,
      };
    },
    { onSelect: ({ path }) => selections.push(path) },
  );
  function findButton(label) {
    function seek(node) {
      if (node.localName === "button" && node.textContent === label) {
        return node;
      }
      return node.childNodes?.map(seek).find(Boolean);
    }
    return seek(host);
  }
  function click(label) {
    const item = findButton(label);
    assert.ok(item, label);
    item.listeners.get("click")();
    return new Promise(setImmediate);
  }
  await mounted.ready;
  const grid = host.lastChild.firstChild;
  const sibling = grid.lastChild.lastChild;
  const branch = grid.lastChild.childNodes.find((row) => row.firstChild?.textContent === "record")
    .lastChild.firstChild;
  const rootText = visibleText(host.lastChild);
  assert.equal(branch.getAttribute("aria-expanded"), "false");
  async function toggleBranch() {
    branch.focus();
    branch.listeners.get("click")();
    await new Promise(setImmediate);
  }
  await toggleBranch();
  const nested = visibleText(host.lastChild);
  assert.ok(nested.includes("id9007199254740993"));
  assert.equal(branch.getAttribute("aria-expanded"), "true");
  assert.equal(host.lastChild.firstChild, grid);
  assert.equal(grid.lastChild.lastChild, sibling);
  assert.equal(document.activeElement, branch);
  await toggleBranch();
  assert.equal(visibleText(host.lastChild), rootText);
  assert.equal(branch.getAttribute("aria-expanded"), "false");
  await toggleBranch();
  assert.equal(visibleText(host.lastChild), nested);
  assert.equal(positions.length, 2);
  await click("More");
  const paged = visibleText(host.lastChild);
  assert.ok(paged.includes("last9007199254740993"));
  assert.equal(grid.lastChild.lastChild, sibling);
  await click("Next page");
  mounted.dispose();
  finish();
  await new Promise(setImmediate);
  assert.ok(!host.textContent.includes("obsolete"));
  const documents = mountNodeTable(host, async ({ document }) => ({
    status: "ready",
    document_count: 2,
    node:
      document === 0
        ? { kind: "object", child_count: 0 }
        : { kind: "string", value: "", child_count: 0 },
  }));
  await documents.ready;
  assert.ok(host.textContent.includes("Empty mapping"));
  const picker = host.firstChild.firstChild;
  picker.value = "1";
  picker.listeners.get("change")();
  await new Promise(setImmediate);
  assert.ok(host.textContent.includes('Value""'));
  documents.dispose();

  let recordDisposed = false;
  const recordGrid = mountNodeTable(
    host,
    async () => ({ status: "too_large", record_table: true }),
    {
      copyRow: async () => {
        assert.fail("The oversized projection is unable to read the row");
      },
      async mountRecords(container, createRowCopy) {
        assert.equal(createRowCopy, undefined);
        container.textContent = "Record grid";
        return {
          dispose() {
            recordDisposed = true;
          },
        };
      },
    },
  );
  await recordGrid.ready;
  assert.ok(host.textContent.includes("Record grid"));
  recordGrid.dispose();
  assert.equal(recordDisposed, true);
  console.log(
    JSON.stringify({ summaries, root: rootText, nested, paged, positions, selections }, null, 2),
  );
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
