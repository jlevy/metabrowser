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
  const rootText = host.lastChild.textContent;
  assert.equal(branch.getAttribute("aria-expanded"), "false");
  async function toggleBranch() {
    branch.focus();
    branch.listeners.get("click")();
    await new Promise(setImmediate);
  }
  await toggleBranch();
  const nested = host.lastChild.textContent;
  assert.ok(nested.includes("id9007199254740993"));
  assert.equal(branch.getAttribute("aria-expanded"), "true");
  assert.equal(host.lastChild.firstChild, grid);
  assert.equal(grid.lastChild.lastChild, sibling);
  assert.equal(document.activeElement, branch);
  await toggleBranch();
  assert.equal(host.lastChild.textContent, rootText);
  assert.equal(branch.getAttribute("aria-expanded"), "false");
  await toggleBranch();
  assert.equal(host.lastChild.textContent, nested);
  assert.equal(positions.length, 2);
  await click("More");
  const paged = host.lastChild.textContent;
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
  console.log(JSON.stringify({ root: rootText, nested, paged, positions, selections }, null, 2));
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
