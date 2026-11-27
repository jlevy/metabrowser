// Browserless session: a tooltip whose anchor is replaced during its delay, and one
// whose page repaints somewhere else.
//
// The app's one tooltip waits 300 ms before it appears. A tree row can be replaced in
// that time, when its folder re-renders, and a detached element reports an all-zero
// rect and never fires the mouseleave that would take the tooltip away. So the tooltip
// used to appear at the top-left corner and stay until another hover (mb-0oxi).
//
// A repaint elsewhere on the page used to take a tree row's tooltip away too, waiting or
// shown, under a pointer that had not moved (mb-alff): the folder view's totals put away
// whatever tooltip was up each time they drew, and the filter bar's rebuild, putting
// focus back on its own control, counted as focus moving. Now a surface puts away only a
// tooltip anchored in it (`hideTooltipWithin`), and focus put back after a rebuild
// removed the element that had it leaves the tooltip be (`hideTooltipOnFocus`), as the
// focus a press on the folder's name gives it does (docs/design-system.md, "Home"). A key
// or press of the reader's after that removal ends the repair (`endTooltipFocusRepair`),
// so the focus it gives still moves.
//
// Moving straight from one annotated element to the next, within the old one's fade, used
// to bring the old one's tooltip back: the "still here" a second show of the new element
// gives (a link card's answer arriving, or the `data-tip-text` delegate firing for a
// child) was taken for the element whose markup was still on screen, so the old tooltip
// stayed up, at the old place, under a pointer resting on the new one. And a second show
// while the first still waited started the 300 ms over. Now "still here" is the element
// whose markup is up (`tooltipShown`), and a show still waiting takes the newest markup
// and keeps its time (docs/design-system.md, "A Tooltip Holds Still").
//
// The tooltip code is lifted verbatim from app.js, which cannot load without a
// document, from its section comment through the document listeners its `data-tip-text`
// delegate registers, with the three helpers that delegate calls. Timers and the
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
  /\n\/\/ ── Custom tooltip[\s\S]*?\ndocument\.addEventListener\("pointerdown", endTooltipFocusRepair, true\);\n/;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/** A top-level function of app.js, verbatim, up to its closing brace. */
function appFunction(name) {
  const match = new RegExp(`\\nfunction ${name}\\(`).exec(appSource);
  assert(match, `app.js ${name} was not found`);
  const start = match.index + 1;
  return appSource.slice(start, appSource.indexOf("\n}\n", start) + 2);
}

const block = appSource.match(TOOLTIP_BLOCK);
assert(block, "the tooltip block was not found in app.js");
const helpers = ["esc", "eventTargetElement", "isPageElement"].map(appFunction).join("\n");

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
    /** Advance to `at` ms after the page began. */
    to(at) {
      this.advance(at - now);
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
    contains: (other) => other === anchor,
    getBoundingClientRect: () =>
      anchor.isConnected
        ? { left: 200, top, bottom: top + 20, width: 80 }
        : { left: 0, top: 0, bottom: 0, width: 0 },
  };
  return anchor;
}

/** A surface of the page, such as the tree or the folder view's totals, holding `inside`. */
function surface(...inside) {
  const element = {
    nodeType: 1,
    isConnected: true,
    contains: (other) => other === element || inside.includes(other),
  };
  return element;
}

/** A control that can take focus, such as the Group by trigger. */
function control() {
  return { nodeType: 1, isConnected: true };
}

// The classes the shell's `instanceof` checks name: `hide(within)` takes an Element, and
// the `data-tip-text` delegate an HTMLElement.
class Element {}
class HTMLElement extends Element {}

/**
 * An element on a line of a surface, at `left`: a link in a document, or a span carrying
 * `tip` as its `data-tip-text`, inside `parent` when it is a child the pointer can cross.
 */
function onLine(left, { tip, text = "", parent = null } = {}) {
  const node = Object.assign(new HTMLElement(), {
    nodeType: 1,
    isConnected: true,
    parentNode: parent,
    dataset: tip === undefined ? {} : { tipText: tip },
    textContent: text,
    classList: { contains: () => false },
    contains(other) {
      for (let at = other; at; at = at.parentNode) {
        if (at === node) {
          return true;
        }
      }
      return false;
    },
    // Only `[data-tip-text]` matches anything here: no stand-in is in the nav's header or a
    // rendered document.
    closest(selector) {
      for (let at = node; at && selector === "[data-tip-text]"; at = at.parentNode) {
        if (at.dataset.tipText !== undefined) {
          return at;
        }
      }
      return null;
    },
    querySelector: () => null,
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({ left, top: 100, bottom: 120, width: 40 }),
  });
  return node;
}

function page() {
  const clock = createClock();
  const element = tooltipElement();
  const listeners = new Map();
  const sandbox = {
    Element,
    HTMLElement,
    clearTimeout: clock.clearTimeout,
    document: {
      addEventListener: (type, listener) => listeners.set(type, listener),
      body: { appendChild() {} },
      createElement: () => element,
    },
    requestAnimationFrame: (callback) => clock.setTimeout(callback, 16),
    setTimeout: clock.setTimeout,
    window: { innerHeight: 800, innerWidth: 1200 },
  };
  vm.createContext(sandbox);
  vm.runInContext(`${helpers}${block[0]}\ninitTooltip();`, sandbox, {
    filename: "app.js (lifted)",
  });
  const read = () => ({
    html: element.innerHTML,
    display: element.style.display ?? "",
    visible: element.classes.has("visible"),
    left: element.style.left ?? "",
    top: element.style.top ?? "",
  });
  // The pointer entering or leaving an element, as the document's capture listeners hear it.
  const pointer = (type, target) => listeners.get(type)({ type, target });
  return { clock, read, sandbox, pointer, tooltip: sandbox.window.MetabrowserTooltip };
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

// Another surface repaints during a tree row's delay, as the folder view's totals do when
// the folder's sums arrive: putting away its own tooltip leaves the row's to appear.
{
  const { clock, read, sandbox } = page();
  const readme = row(100);
  const totals = surface(row(500));
  sandbox.showTooltip("<b>size</b>", readme);
  clock.advance(150);
  sandbox.hideTooltipWithin(totals);
  clock.advance(150 + 16);
  const shown = read();
  assert(shown.display === "block" && shown.visible, "another surface's repaint took the tooltip");
  // And again while it is up: it stays up.
  sandbox.hideTooltipWithin(totals);
  clock.advance(150 + 16);
  const stillUp = read();
  assert(stillUp.display === "block" && stillUp.visible, "another surface's repaint hid it");
  transcript["another surface's repaint leaves a row's tooltip"] = { shown, stillUp };
}

// A surface that repaints its own anchor puts its tooltip away, waiting or shown.
{
  const { clock, read, sandbox } = page();
  const segment = row(500);
  const totals = surface(segment);
  sandbox.showTooltip("<b>Python</b>", segment);
  clock.advance(150);
  sandbox.hideTooltipWithin(totals);
  clock.advance(300 + 16);
  const waiting = read();
  assert(waiting.display !== "block" && !waiting.visible, "a waiting tooltip survived its repaint");
  sandbox.showTooltip("<b>Python</b>", segment);
  clock.advance(300 + 16);
  const up = read();
  sandbox.hideTooltipWithin(totals);
  clock.advance(150);
  const afterFade = read();
  assert(up.visible, "the segment's tooltip did not appear");
  assert(
    afterFade.display === "none" && !afterFade.visible,
    "a shown tooltip survived its repaint",
  );
  transcript["a surface's repaint puts its own tooltip away"] = { waiting, up, afterFade };
}

// A tooltip whose anchor has left the document belongs to no surface still on the page,
// so any surface's hide puts it away, even one made after the anchor was removed.
{
  const { clock, read, sandbox } = page();
  const removed = row(100);
  sandbox.showTooltip("<b>size</b>", removed);
  clock.advance(300 + 16);
  const up = read();
  removed.isConnected = false;
  sandbox.hideTooltipWithin(surface());
  clock.advance(150);
  const afterFade = read();
  assert(up.visible, "the row's tooltip did not appear");
  assert(afterFade.display === "none" && !afterFade.visible, "an orphaned tooltip stayed up");
  transcript["any surface's hide puts away a tooltip whose anchor is gone"] = { up, afterFade };
}

// The filter bar rebuilds during a tree row's delay and puts focus back on its own
// trigger, which the rebuild replaced: focus has not moved, so the tooltip appears.
{
  const { clock, read, sandbox } = page();
  const trigger = control();
  sandbox.hideTooltipOnFocus({ target: trigger });
  sandbox.showTooltip("<b>size</b>", row(100));
  clock.advance(150);
  trigger.isConnected = false;
  const rebuilt = control();
  sandbox.hideTooltipOnFocus({ target: rebuilt });
  clock.advance(150 + 16);
  const shown = read();
  assert(shown.display === "block" && shown.visible, "a focus repair took the tooltip");
  // Focus moving on from there, as Tab or an arrow key moves it, puts the tooltip away.
  sandbox.hideTooltipOnFocus({ target: control() });
  const moved = read();
  clock.advance(150);
  const afterFade = read();
  assert(!moved.visible && afterFade.display === "none", "focus moved and the tooltip stayed");
  transcript["focus put back after a rebuild leaves the tooltip"] = { shown, moved, afterFade };
}

// A key of the reader's causes the rebuild: its keydown comes while the trigger is still in
// the document, so the focus the rebuild puts back is still the repair.
{
  const { clock, read, sandbox } = page();
  const trigger = control();
  sandbox.hideTooltipOnFocus({ target: trigger });
  sandbox.showTooltip("<b>size</b>", row(100));
  clock.advance(150);
  sandbox.endTooltipFocusRepair();
  trigger.isConnected = false;
  sandbox.hideTooltipOnFocus({ target: control() });
  clock.advance(150 + 16);
  const shown = read();
  assert(shown.display === "block" && shown.visible, "a key before the rebuild ended its repair");
  transcript["a rebuild the reader's key causes is still a repair"] = { shown };
}

// A rebuild removes the focused control and focuses nothing, as pressing the filter bar's
// Clear does: focus falls to the page with no focusin. A tree row's tooltip comes up, and
// the reader's next key, a Tab, ends the repair before the focus it gives, so that focus
// moves and puts the tooltip away. A press's pointerdown does the same.
{
  const { clock, read, sandbox } = page();
  const clear = control();
  sandbox.hideTooltipOnFocus({ target: clear });
  clear.isConnected = false;
  sandbox.showTooltip("<b>size</b>", row(100));
  clock.advance(300 + 16);
  const up = read();
  sandbox.endTooltipFocusRepair();
  sandbox.hideTooltipOnFocus({ target: control() });
  clock.advance(150);
  const afterTab = read();
  assert(up.display === "block" && up.visible, "the row's tooltip did not appear");
  assert(
    afterTab.display === "none" && !afterTab.visible,
    "the reader's Tab after focus was dropped left the tooltip up",
  );
  transcript["the reader's key after a rebuild dropped focus moves it"] = { up, afterTab };
}

// The rebuild replaces the very control whose tooltip is up, as the bar's drawer toggle is
// replaced with the pointer resting on it: the repair puts that tooltip away, since its
// anchor has left the document and will never hear the mouseleave that ends it.
{
  const { clock, read, sandbox } = page();
  const toggle = row(40);
  sandbox.hideTooltipOnFocus({ target: toggle });
  sandbox.showTooltip("<b>Filters</b>", toggle);
  clock.advance(300 + 16);
  const up = read();
  toggle.isConnected = false;
  sandbox.hideTooltipOnFocus({ target: row(40) });
  clock.advance(150);
  const afterRepair = read();
  assert(up.display === "block" && up.visible, "the toggle's tooltip did not appear");
  assert(
    afterRepair.display === "none" && !afterRepair.visible,
    "a repair left up a tooltip whose anchor the rebuild removed",
  );
  transcript["a repair puts away a tooltip whose anchor the rebuild removed"] = {
    up,
    afterRepair,
  };
}

// Focus moving between two controls still in the document, during the delay: the tooltip
// never appears.
{
  const { clock, read, sandbox } = page();
  sandbox.hideTooltipOnFocus({ target: control() });
  sandbox.showTooltip("<b>size</b>", row(100));
  clock.advance(150);
  sandbox.hideTooltipOnFocus({ target: control() });
  clock.advance(300 + 16);
  const atDelay = read();
  assert(atDelay.display !== "block" && !atDelay.visible, "a tooltip appeared after focus moved");
  transcript["focus moving during the delay puts the tooltip away"] = { atDelay };
}

// Straight from one link's card to the next, within the card's fade, as a link card's
// rests call the tooltip (static/link-previews.js): the pointer leaving the first puts its
// card away, the second's rest shows its card at once, and the second's title arriving while
// that card waits shows it again. The second's card, with its title, appears at its own
// place on its own time, and stays while the pointer rests; the first's never comes back.
{
  const { clock, read, tooltip } = page();
  const one = onLine(100);
  const two = onLine(300);
  tooltip.show("<b>#1</b> Title of 1", one);
  clock.to(700);
  const first = read();
  clock.to(800);
  tooltip.hide(one);
  tooltip.show("<b>#2</b>", two);
  clock.to(1051);
  tooltip.show("<b>#2</b> Title of 2", two);
  clock.to(1099);
  const waiting = read();
  clock.to(800 + 300 + 16);
  const second = read();
  clock.to(3000);
  const resting = read();
  assert(first.visible && first.left === "70px", "the first card did not come up on its link");
  assert(!waiting.visible, "the first card came back while the second waited");
  assert(
    second.visible && second.html === "<b>#2</b> Title of 2" && second.left === "270px",
    `the second link showed ${JSON.stringify(second)}`,
  );
  assert(JSON.stringify(resting) === JSON.stringify(second), "the second card did not stay");
  transcript["straight to the next link within the fade shows the next card"] = {
    first,
    waiting,
    second,
    resting,
  };
}

// The same handover through the document's own `data-tip-text` delegate: from X straight to
// Y, then onto a child of Y, whose entering fires the delegate for Y again. Y's tip appears
// at Y on Y's time; X's never comes back.
{
  const { clock, read, pointer } = page();
  const x = onLine(100, { tip: "Tip of X", text: "Xxxxx x" });
  const y = onLine(300, { tip: "Tip of Y", text: "Yyyyy yyyy" });
  const child = onLine(320, { parent: y, text: "yyyy" });
  pointer("mouseenter", x);
  clock.to(700);
  const atX = read();
  pointer("mouseleave", x);
  pointer("mouseenter", y);
  clock.to(760);
  pointer("mouseenter", child);
  clock.to(776);
  const atChild = read();
  clock.to(700 + 300 + 16);
  const atY = read();
  clock.to(1600);
  const resting = read();
  assert(atX.visible && atX.html === "Tip of X", "X's tip did not come up");
  assert(!atChild.visible, "X's tip came back when the pointer crossed Y's child");
  assert(
    atY.visible && atY.html === "Tip of Y" && atY.left === "270px",
    `resting on Y showed ${JSON.stringify(atY)}`,
  );
  assert(JSON.stringify(resting) === JSON.stringify(atY), "Y's tip did not stay");
  transcript["from X to Y and onto Y's child shows Y's tip"] = { atX, atChild, atY, resting };
}

// A completed refresh updates the Refresh tooltip, even if the pointer reached it while
// an unrelated card was still fading. The new data belongs to the new anchor; it cannot
// repaint the old card before Refresh's delay ends.
{
  const { clock, read, pointer, tooltip } = page();
  const link = onLine(100);
  const refresh = onLine(300, { tip: "Last fetched 2 min ago", text: "Refresh" });
  tooltip.show("<b>#1</b> Review this pull request", link);
  clock.to(700);
  tooltip.hide(link);
  pointer("mouseenter", refresh);
  clock.to(750);
  refresh.dataset.tipText = "Refreshed just now\n3 requests · 900 B · 250ms · GitHub CLI";
  tooltip.updateText(refresh);
  const waiting = read();
  assert(
    waiting.html === "<b>#1</b> Review this pull request" && waiting.left === "70px",
    "a timing update repainted a link card waiting to leave",
  );
  clock.to(700 + 300 + 16);
  const complete = read();
  assert(
    complete.visible &&
      complete.left === "270px" &&
      complete.html ===
        'Refreshed just now<div class="tip-detail">3 requests · 900 B · 250ms · GitHub CLI</div>',
    "Refresh did not appear at its anchor with the newly completed timing",
  );
  refresh.dataset.tipText = "Refreshed just now\n2 requests · 0 B · 90ms · GitHub CLI";
  tooltip.updateText(refresh);
  const shownUpdate = read();
  assert(
    shownUpdate.visible && shownUpdate.left === complete.left && shownUpdate.html.includes("90ms"),
    "Refresh did not update the tooltip currently shown for its own anchor",
  );
  transcript["Refresh timing keeps the fading link card and updates its own tooltip"] = {
    waiting,
    complete,
    shownUpdate,
  };
}

// A show again while the first still waits, as a link card's title arriving 251 ms into a
// rest is: the tooltip appears when the first show's delay ends, with the newer markup.
// Once it is up, a show again with other markup is "still here" and changes nothing: what
// arrives later waits for the next appearance (docs/design-system.md, "A Tooltip Holds
// Still").
{
  const { clock, read, tooltip } = page();
  const link = onLine(100);
  tooltip.show("<b>#12</b>", link);
  clock.to(251);
  tooltip.show("<b>#12</b> Keep the tail", link);
  clock.to(299);
  const before = read();
  clock.to(300 + 16);
  const onTime = read();
  tooltip.show("<b>#12</b> Keep the tail, and more", link);
  clock.to(1500);
  const later = read();
  assert(before.display === "", "the tooltip appeared before its delay");
  assert(
    onTime.visible && onTime.html === "<b>#12</b> Keep the tail",
    `at the first show's delay the tooltip read ${JSON.stringify(onTime)}`,
  );
  assert(JSON.stringify(later) === JSON.stringify(onTime), "a tooltip already up changed");
  transcript["a show again while waiting keeps the first show's time"] = {
    before,
    onTime,
    later,
  };
}

// Back onto the first element before the second's delay ends: the first's markup never
// left, so it is still here, and its own surface's hide puts it away. Leaving during a delay
// and coming back starts the delay again.
{
  const { clock, read, tooltip } = page();
  const one = onLine(100);
  const two = onLine(300);
  tooltip.show("<b>#1</b>", one);
  clock.to(700);
  tooltip.hide(one);
  tooltip.show("<b>#2</b>", two);
  clock.to(760);
  tooltip.hide(two);
  tooltip.show("<b>#1</b>", one);
  const back = read();
  clock.to(1500);
  const resting = read();
  tooltip.hide(one);
  clock.to(1650);
  const putAway = read();
  tooltip.show("<b>#2</b>", two);
  clock.to(1700);
  tooltip.hide(two);
  clock.to(1750);
  tooltip.show("<b>#2</b>", two);
  clock.to(1750 + 299);
  const again = read();
  clock.to(1750 + 300 + 16);
  const afterDelay = read();
  assert(back.visible && back.html === "<b>#1</b>", "the first tooltip was not still here");
  assert(resting.visible && resting.left === "70px", "the second's delay replaced the first");
  assert(putAway.display === "none", "the first's own surface did not put it away");
  assert(again.display !== "block", "a show after leaving during the delay kept the old time");
  assert(afterDelay.visible && afterDelay.html === "<b>#2</b>", "coming back showed nothing");
  transcript["back onto the first within the second's delay keeps the first"] = {
    back,
    resting,
    putAway,
    again,
    afterDelay,
  };
}

process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
