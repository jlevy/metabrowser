// Browserless session: a tooltip whose anchor is replaced during its delay.
//
// The app's one tooltip waits 300 ms before it appears. A tree row can be replaced in
// that time, when its folder re-renders, and a detached element reports an all-zero
// rect and never fires the mouseleave that would take the tooltip away. So the tooltip
// used to appear at the top-left corner and stay until another hover (mb-0oxi).
//
// The tooltip code is lifted verbatim from app.js, which cannot load without a
// document, from its section comment to the block that publishes it. Timers and the
// animation frame are this file's, so each step says exactly how much time has passed;
// elements are stand-ins that report whether they are connected and where they are.
//
// Each step prints what the tooltip element holds. Exits 1 on a failed invariant.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf8");

const TOOLTIP_BLOCK =
  /\n\/\/ ── Custom tooltip[\s\S]*?(?=\nif \(typeof window !== "undefined"\) \{\n {2}window\.MetabrowserTooltip)/;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const block = appSource.match(TOOLTIP_BLOCK);
assert(block, "the tooltip block was not found in app.js");

/** A clock this file advances: `setTimeout` and `requestAnimationFrame` run on it. */
function createClock() {
  let now = 0;
  let nextId = 1;
  const timers = new Map();
  return {
    setTimeout(callback, delay) {
      const id = nextId++;
      timers.set(id, { at: now + delay, callback });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    advance(ms) {
      const end = now + ms;
      for (;;) {
        const due = [...timers.entries()]
          .filter(([, timer]) => timer.at <= end)
          .sort((left, right) => left[1].at - right[1].at || left[0] - right[0])[0];
        if (!due) {
          break;
        }
        timers.delete(due[0]);
        now = due[1].at;
        due[1].callback();
      }
      now = end;
    },
  };
}

function tooltipElement() {
  const classes = new Set();
  return {
    className: "",
    innerHTML: "",
    style: {},
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
    },
    classes,
    getBoundingClientRect: () => ({ width: 100, height: 20 }),
  };
}

/** A tree row: where a connected one is, and the all-zero rect a detached one reports. */
function row(top) {
  const anchor = {
    nodeType: 1,
    isConnected: true,
    getBoundingClientRect: () =>
      anchor.isConnected
        ? { left: 200, top, bottom: top + 20, width: 80 }
        : { left: 0, top: 0, bottom: 0, width: 0 },
  };
  return anchor;
}

function page() {
  const clock = createClock();
  const element = tooltipElement();
  const sandbox = {
    clearTimeout: clock.clearTimeout,
    document: { body: { appendChild() {} }, createElement: () => element },
    requestAnimationFrame: (callback) => clock.setTimeout(callback, 16),
    setTimeout: clock.setTimeout,
    window: { innerHeight: 800, innerWidth: 1200 },
  };
  vm.createContext(sandbox);
  vm.runInContext(`${block[0]}\ninitTooltip();`, sandbox, { filename: "app.js (lifted)" });
  const read = () => ({
    html: element.innerHTML,
    display: element.style.display ?? "",
    visible: element.classes.has("visible"),
    left: element.style.left ?? "",
    top: element.style.top ?? "",
  });
  return { clock, read, sandbox };
}

const transcript = {};

// The ordinary hover: nothing for 300 ms, then the tooltip under its row.
{
  const { clock, read, sandbox } = page();
  sandbox.showTooltip("<b>size</b>", row(100));
  clock.advance(299);
  const during = read();
  clock.advance(1 + 16);
  const shown = read();
  assert(during.display === "", "a tooltip appeared before its delay");
  assert(shown.display === "block" && shown.visible, "a connected row's tooltip did not appear");
  assert(shown.top === "126px", `a connected row's tooltip landed at ${shown.top}`);
  transcript["a row still in the document shows its tooltip under it"] = { during, shown };
}

// The bug: the row is replaced during the delay.
{
  const { clock, read, sandbox } = page();
  const replaced = row(100);
  sandbox.showTooltip("<b>size</b>", replaced);
  clock.advance(150);
  replaced.isConnected = false;
  clock.advance(150 + 16);
  const atDelay = read();
  clock.advance(150);
  const afterFade = read();
  assert(atDelay.html === "", "a replaced row's tooltip wrote its content");
  assert(atDelay.left === "" && atDelay.top === "", "a replaced row's tooltip was positioned");
  assert(!atDelay.visible, "a replaced row's tooltip became visible");
  assert(afterFade.display === "none", "a replaced row's tooltip was not put away");
  transcript["a row replaced during the delay shows nothing"] = { atDelay, afterFade };

  // The row that replaced it is hovered next, on the ordinary delay.
  sandbox.showTooltip("<b>new row</b>", row(300));
  clock.advance(300 + 16);
  const nextHover = read();
  assert(nextHover.html === "<b>new row</b>" && nextHover.visible, "the next hover did not show");
  assert(nextHover.top === "326px", `the next hover landed at ${nextHover.top}`);
  transcript["the next hover shows normally"] = { nextHover };
}

// A tooltip already up for one row, then a hover on a row replaced during its delay:
// the first row's tooltip does not stay behind, since nothing would take it away.
{
  const { clock, read, sandbox } = page();
  sandbox.showTooltip("<b>first</b>", row(100));
  clock.advance(300 + 16);
  const up = read();
  const second = row(140);
  sandbox.showTooltip("<b>second</b>", second);
  second.isConnected = false;
  clock.advance(300 + 16);
  const atDelay = read();
  clock.advance(150);
  const afterFade = read();
  assert(up.visible, "the first row's tooltip was not up");
  assert(atDelay.html === "<b>first</b>", "the replaced row's content was written");
  assert(!atDelay.visible, "the first row's tooltip stayed up");
  assert(afterFade.display === "none", "the first row's tooltip was not put away");
  transcript["a tooltip already up is put away too"] = { up, atDelay, afterFade };
}

// A caller with no anchor has nothing to leave the document, and keeps its behavior.
{
  const { clock, read, sandbox } = page();
  sandbox.showTooltip("<b>no anchor</b>", null);
  clock.advance(300 + 16);
  const shown = read();
  assert(shown.display === "block" && shown.visible, "an anchorless tooltip did not appear");
  transcript["a tooltip with no anchor still appears"] = { shown };
}

process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
