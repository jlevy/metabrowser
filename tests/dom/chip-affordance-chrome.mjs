// Whether a chip says it is clickable, in the running app and headless Chrome
// (docs/design-system.md, "Clickable and Static Chips").
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/chip-affordance-chrome.mjs GITHUB_BASE METAB ROOT PORT STATE_DIR
//
// tests/test_chip_affordance_chrome.py serves the GitHub stand-in, with native stacks, at
// GITHUB_BASE, and writes ROOT, a checkout of a SQLite database whose orders reference its
// users, a Markdown document whose images the page does not load, and a compressed file,
// with a branch and a tag, which this session serves untrusted with METAB on PORT, its
// cache and configuration in STATE_DIR.
// The test owns the profile directory and stops this process's group, Chrome and the
// folder's server included, however the run ends (tests/process_group.py).
//
// On every surface it opens, in the light theme and the dark, it finds each chip by its
// shape, not its class: a box about a line tall, with a border or a ground of its own,
// holding a label, and a count at most. Which control a chip is is what the pointer hits at its middle: the
// chip itself, a link or button whose whole visible content is the chip, a button laid over
// it (a history row's ref menu), a larger control the chip is a part of (a row), or none.
// Then, moving the pointer onto it and forcing keyboard focus on its control:
//
// - a clickable chip, the first three, shows the pointer, is underlined by nothing between
//   its text and its control at rest, under the pointer, or focused, paints a different
//   ground under the pointer unless it is selected, keeps its text at 4.5:1 on that ground,
//   and its control draws the one focus ring;
// - a static chip, one in no control or a disabled one, paints the same pixels under the
//   pointer as at rest, shows no pointer, and is underlined by nothing;
// - a chip that is a part of a larger control is underlined by nothing.
//
// The ground is a pixel the page paints inside the chip's starting padding, read from a
// one-pixel screenshot, so what is held is what a reader sees, whatever rule paints it. The
// text's ink is the chip's own color with whatever the page lays over the chip composited
// on it, by a canvas, as the page composites it.
import { spawn } from "node:child_process";
import path from "node:path";
import zlib from "node:zlib";
import { launchChrome } from "./chrome-session.mjs";

// The theme to read, or both: each is its own test (tests/test_chip_affordance_chrome.py).
const [githubBase, metab, root, port, state, onlyTheme] = process.argv.slice(2);
if (!githubBase || !metab || !root || !port || !state) {
  throw new Error("usage: chip-affordance-chrome.mjs GITHUB_BASE METAB ROOT PORT STATE_DIR");
}
const folderBase = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
// WCAG's floor for text, which every ink a chip sets is held to (docs/design-system.md,
// "Badges", "Branch Chips").
const TEXT_CONTRAST = 4.5;
// A ground under the pointer is a different ground when a channel moved by more than this,
// in 0-255: past the screenshot's rounding of one color to bytes.
const GROUND_STEP = 2;
// Each wait's bound: a paint, or a record or a stack the stand-in's fake gh answers, which
// takes a few seconds on a loaded machine.
const STEP_MS = 30000;

async function serveFolder() {
  const server = spawn(
    metab,
    [
      root,
      // Untrusted, so a document's images over `http` are the chips that stand for them.
      "--untrusted",
      "--no-open",
      "--port",
      port,
      "--cache-dir",
      path.join(state, "cache"),
      "--config-dir",
      path.join(state, "config"),
    ],
    {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING", METABROWSER_EVENT_LOG: "0" },
    },
  );
  const exited = new Promise((resolve) => server.once("exit", resolve));
  let output = "";
  await new Promise((resolve, reject) => {
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), STEP_MS);
    const read = (chunk) => {
      output += chunk;
      if (output.includes("Serving ") && output.includes(folderBase)) {
        clearTimeout(bound);
        resolve();
      }
    };
    server.stdout.on("data", read);
    server.stderr.on("data", read);
    server.once("exit", () => reject(new Error(`server exited: ${output}`)));
  });
  return {
    async stop() {
      server.kill("SIGTERM");
      await Promise.race([exited, sleep(10000)]);
      if (server.exitCode === null) {
        server.kill("SIGKILL");
        await exited;
      }
    },
  };
}

// In the page: every chip-shaped box under *scope*, each marked `data-chip-probe` with its
// index, and what each is. A chip is found by its shape: an element about a line tall, with a
// border or a ground of its own, holding text. A box of that shape that holds two controls or
// more is a group of chips joined into one frame, `.chip-group[data-layout="joined"]`, and
// each control in it is a chip; one that holds a single control filling most of it is that
// control's frame, and the control is the chip. A box that holds more than two runs of text,
// a label and a count, is a row of parts, not a chip. The control families that are not chips (a labelled button,
// an icon button, a tab, a menu row or segment, a field, a fold), rows of a list, a tree, a
// menu, or a table, code in prose, a tooltip, and what is hidden are not chips.
const FIND = `((scope) => {
  for (const marked of document.querySelectorAll("[data-chip-probe], [data-chip-control]")) {
    marked.removeAttribute("data-chip-probe");
    marked.removeAttribute("data-chip-control");
  }
  const scopes = [...document.querySelectorAll(scope)];
  if (scopes.length === 0) return null;
  const INTERACTIVE = "a[href], button, summary, [role=button], [role=link], [role=radio], [role=checkbox]";
  const NOT_CHIPS = ".btn, .icon-btn, .tab-btn, .menu-item, .menu-seg, .field, input, select, textarea, " +
    "summary.section-disclosure-trigger, .fold-expander, [role=tooltip], li, tr, td, th, code, kbd, samp, mark, pre, " +
    "[role=row], [role=treeitem], [role=option], [role=menuitem], [role=menuitemradio], [role=menuitemcheckbox], .sr-only";
  const opaque = (color) => color !== "transparent" && !/rgba\\(.*,\\s*0\\)$/.test(color) && !/\\/\\s*0\\)$/.test(color);
  const shown = (element) => {
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return box.width > 0 && box.height > 0 && style.visibility === "visible" && Number(style.opacity) >= 0.05;
  };
  const chips = new Set();
  for (const element of scopes.flatMap((each) => [...each.querySelectorAll("*")])) {
    if (element instanceof SVGElement || element.matches(NOT_CHIPS) || element.closest("[hidden], [aria-hidden=true], .tooltip, code, pre")) continue;
    const box = element.getBoundingClientRect();
    if (box.height < 10 || box.height > 26 || box.width < 8 || box.width > 400 || !shown(element)) continue;
    const style = getComputedStyle(element);
    const bordered = parseFloat(style.borderTopWidth) > 0 && style.borderTopStyle !== "none" && opaque(style.borderTopColor);
    const grounded = opaque(style.backgroundColor) || style.backgroundImage !== "none";
    if ((!bordered && !grounded) || element.textContent.trim() === "") continue;
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const holders = new Set();
    for (let text = walker.nextNode(); text !== null; text = walker.nextNode()) {
      if (text.textContent.trim() !== "") holders.add(text.parentElement);
    }
    if (holders.size > 2) continue;
    const controls = [...element.querySelectorAll(INTERACTIVE)].filter((each) => shown(each) && each.textContent.trim() !== "");
    const framed = controls.length === 1 && controls[0].getBoundingClientRect().width >= box.width / 2;
    if ((controls.length >= 2 || framed) && !element.matches(INTERACTIVE)) {
      for (const each of controls) chips.add(each);
    } else {
      chips.add(element);
    }
  }
  const pathOf = (element) => {
    const steps = [];
    for (let node = element; node.parentElement !== null; node = node.parentElement) {
      steps.unshift(node.tagName.toLowerCase() + ":nth-child(" + ([...node.parentElement.children].indexOf(node) + 1) + ")");
    }
    return ":root > " + steps.join(" > ");
  };
  return [...chips].map((chip, index) => {
    chip.dataset.chipProbe = String(index);
    return {
      index,
      path: pathOf(chip),
      what: chip.tagName.toLowerCase() + [...chip.classList].slice(0, 4).map((name) => "." + name).join(""),
      text: chip.textContent.trim().replace(/\\s+/g, " ").slice(0, 40),
    };
  });
})`;

// In the page: chip *index* brought into view, where its middle is, where its ground is, a
// pixel inside its starting padding, and where the ground beside it is, three pixels before
// it, past the ring `HEAD` draws a pixel out from a ref chip.
const PLACE = `((index, path) => {
  const chip = document.querySelector('[data-chip-probe="' + index + '"]') ?? document.querySelector(path);
  if (chip === null) return null;
  chip.dataset.chipProbe = String(index);
  chip.scrollIntoView({ block: "center", inline: "nearest" });
  const box = chip.getBoundingClientRect();
  const style = getComputedStyle(chip);
  const start = parseFloat(style.borderLeftWidth) + Math.max(1, Math.min(4, parseFloat(style.paddingLeft) / 2));
  // What the pointer reaches at its middle with nothing hovered is the chip, unless a box
  // around it clips it away, as a closed drawer does its chips.
  const middle = { x: box.left + box.width / 2, y: box.top + box.height / 2 };
  const reached = document.elementFromPoint(middle.x, middle.y);
  return {
    middle,
    ground: { x: Math.floor(box.left + start), y: Math.floor(box.top + box.height / 2) },
    beside: { x: Math.max(0, Math.floor(box.left) - 3), y: Math.floor(box.top + box.height / 2) },
    shown: box.top >= 0 && box.bottom <= innerHeight && box.left >= 3 && box.right <= innerWidth &&
      reached !== null && chip.contains(reached),
  };
})`;

// In the page: chip *index* in the state the pointer and the focus leave it, which control
// the pointer reaches at its middle, and how each part between its text and that control
// reads.
const READ = `((index, path, middle) => {
  const chip = document.querySelector('[data-chip-probe="' + index + '"]') ?? document.querySelector(path);
  if (chip === null) return null;
  chip.dataset.chipProbe = String(index);
  const INTERACTIVE = 'a[href], button, summary, [role=button], [role=link], [role=menuitem], ' +
    '[role=menuitemradio], [role=menuitemcheckbox], [role=option], [role=tab], [role=treeitem], [role=radio], [role=checkbox]';
  const hit = document.elementFromPoint(middle.x, middle.y);
  const reached = hit?.closest(INTERACTIVE) ?? null;
  const around = chip.closest(INTERACTIVE);
  let kind = "static";
  let control = null;
  if (reached !== null && !reached.contains(chip) && !chip.contains(reached)) {
    kind = "overlay";
    control = reached;
  } else if (around === chip) {
    kind = "self";
    control = chip;
  } else if (around !== null) {
    // The chip is its control's whole visible content when every text and every glyph the
    // control shows is the chip's.
    const walker = document.createTreeWalker(around, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let outside = false;
    for (let node = walker.nextNode(); node !== null && !outside; node = walker.nextNode()) {
      if (chip.contains(node)) continue;
      const element = node.nodeType === 1 ? node : node.parentElement;
      const shown = element.getClientRects().length > 0 && getComputedStyle(element).visibility === "visible" &&
        element.closest(".sr-only") === null;
      if (!shown) continue;
      const text = node.nodeType === 3 && node.textContent.trim() !== "";
      const glyph = node.nodeType === 1 && (node.tagName.toLowerCase() === "svg" || node.tagName === "IMG") &&
        node.getBoundingClientRect().width > 0;
      outside = text || glyph;
    }
    kind = outside ? "part" : "content";
    control = around;
  }
  for (const marked of document.querySelectorAll('[data-chip-control="' + index + '"]')) {
    marked.removeAttribute("data-chip-control");
  }
  if (control !== null) control.dataset.chipControl = String(index);
  const states = [chip, control].filter(Boolean);
  const disabled = states.some((node) => node.matches(":disabled, [aria-disabled=true]"));
  const selected = states.some((node) => node.matches("[aria-checked=true], [aria-pressed=true], [aria-selected=true], [aria-expanded=true], [data-active=true]"));
  // Every element from the chip's text up to its control, and the control laid over it.
  const chain = [];
  for (let node = chip; node !== null; node = node.parentElement) {
    chain.push(node);
    if (control === null || node === control || kind === "overlay") break;
  }
  if (kind === "overlay") chain.push(control);
  const underlined = chain
    .filter((node) => getComputedStyle(node).textDecorationLine.includes("underline"))
    .map((node) => node.tagName.toLowerCase() + [...node.classList].slice(0, 2).map((name) => "." + name).join(""));
  // The chip's text: the deepest element holding its first words.
  const walker = document.createTreeWalker(chip, NodeFilter.SHOW_TEXT);
  let words = walker.nextNode();
  while (words !== null && words.textContent.trim() === "") words = walker.nextNode();
  const holder = words?.parentElement ?? chip;
  // What the page lays over the chip's text: the chip's own ::after, and the control laid over
  // it, each composited on the ink as the page composites them.
  const layers = [];
  const after = getComputedStyle(chip, "::after");
  if (after.content !== "none" && after.content !== "normal") layers.push(after.backgroundColor);
  if (kind === "overlay") layers.push(getComputedStyle(control).backgroundColor);
  const canvas = (window.__chipCanvas ??= Object.assign(document.createElement("canvas"), { width: 1, height: 1 }));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.globalCompositeOperation = "copy";
  context.fillStyle = getComputedStyle(holder).color;
  context.fillRect(0, 0, 1, 1);
  context.globalCompositeOperation = "source-over";
  for (const layer of layers) {
    context.fillStyle = layer;
    context.fillRect(0, 0, 1, 1);
  }
  const ink = [...context.getImageData(0, 0, 1, 1).data];
  const ringed = control ?? chip;
  const ringStyle = (node) => {
    const style = getComputedStyle(node);
    return { style: style.outlineStyle, width: style.outlineWidth, color: style.outlineColor };
  };
  return {
    kind,
    disabled,
    selected,
    control: control === null ? null : control.tagName.toLowerCase() + [...control.classList].slice(0, 2).map((name) => "." + name).join(""),
    cursor: hit === null ? null : getComputedStyle(hit).cursor,
    underlined,
    ink,
    rings: [ringStyle(ringed), ringStyle(chip)],
    // The chip's shape and its hover layer's: a layer stays inside the chip when the chip
    // clips it, or when it takes the chip's corners.
    shape: (() => {
      const own = getComputedStyle(chip);
      const layer = getComputedStyle(chip, "::after");
      return {
        layered: layer.content !== "none" && layer.content !== "normal",
        clips: own.overflow !== "visible" || own.clipPath !== "none",
        corners: own.borderRadius,
        layerCorners: layer.borderRadius,
      };
    })(),
  };
})`;

// In the page: the one focus ring, as an outline of it computes.
const RING = `(() => {
  const probe = document.createElement("span");
  probe.style.cssText = "outline: var(--focus-ring-width) solid var(--focus-ring-color)";
  document.body.append(probe);
  const style = getComputedStyle(probe);
  const ring = { style: style.outlineStyle, width: style.outlineWidth, color: style.outlineColor };
  probe.remove();
  return ring;
})()`;

// In the page: resolves once no transition is running, two frames later.
const SETTLED = `new Promise((resolve) => {
  const deadline = performance.now() + 1500;
  const step = () => {
    const running = document.getAnimations().some((animation) => animation instanceof CSSTransition && animation.playState === "running");
    if (!running || performance.now() > deadline) {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
    } else {
      setTimeout(step, 16);
    }
  };
  step();
})`;

const luminance = ([red, green, blue]) => {
  const linear = (channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
};
const contrast = (first, second) => {
  const [lighter, darker] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
};
const differs = (first, second) =>
  first.some((channel, at) => Math.abs(channel - second[at]) > GROUND_STEP);

async function main() {
  const profiles = process.env.CHROME_PROFILES;
  if (!process.env.CHROME_BIN || !profiles) {
    throw new Error("CHROME_BIN and CHROME_PROFILES are required");
  }
  const folder = await serveFolder();
  phase("folder served");
  /** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
  let chrome = null;
  const seen = {};
  try {
    chrome = await launchChrome(process.env.CHROME_BIN, { profiles, width: 1280, height: 900 });
    const browser = chrome;
    phase("chrome");
    const { evaluate, send, waitFor } = browser;
    await send("Page.enable");
    await send("DOM.enable");
    await send("CSS.enable");
    const settle = () => evaluate(SETTLED);
    const away = async () => {
      await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1279, y: 899 });
      await settle();
    };
    const pixel = async ({ x, y }) => {
      const { data } = await send("Page.captureScreenshot", {
        format: "png",
        clip: { x, y, width: 1, height: 1, scale: 1 },
      });
      const png = Buffer.from(data, "base64");
      const idat = [];
      for (let at = 8; at < png.length; ) {
        const length = png.readUInt32BE(at);
        const type = png.toString("latin1", at + 4, at + 8);
        if (type === "IDAT") {
          idat.push(png.subarray(at + 8, at + 8 + length));
        }
        at += 12 + length;
      }
      const raw = zlib.inflateSync(Buffer.concat(idat));
      return [raw[1], raw[2], raw[3]];
    };
    const click = async (selector) => {
      await waitFor(`document.querySelector(${JSON.stringify(selector)}) !== null`, STEP_MS);
      await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    };
    const nodeOf = async (selector) => {
      const { root: documentNode } = await send("DOM.getDocument", { depth: 0 });
      const { nodeId } = await send("DOM.querySelector", { nodeId: documentNode.nodeId, selector });
      return nodeId;
    };

    // Every chip under *scope* on the surface *name*, in *theme*.
    const audit = async (name, theme, scope) => {
      await away();
      const found = await evaluate(`(${FIND})(${JSON.stringify(scope)})`);
      check(`${name} (${theme}): the surface is drawn`, found !== null, scope);
      if (found === null) {
        return;
      }
      const ring = await evaluate(RING);
      const kinds = {};
      for (const chip of found) {
        const where = `${name} (${theme}): ${chip.what} "${chip.text}"`;
        const place = await evaluate(`(${PLACE})(${chip.index}, ${JSON.stringify(chip.path)})`);
        if (place === null || !place.shown) {
          if (process.env.CHIP_DEBUG) {
            process.stderr.write(`chip ${where}: not in view ${JSON.stringify(place)}\n`);
          }
          continue;
        }
        await away();
        const restGround = await pixel(place.ground);
        const restBeside = await pixel(place.beside);
        const rest = await evaluate(
          `(${READ})(${chip.index}, ${JSON.stringify(chip.path)}, ${JSON.stringify(place.middle)})`,
        );
        await send("Input.dispatchMouseEvent", { type: "mouseMoved", ...place.middle });
        await settle();
        const hoverGround = await pixel(place.ground);
        const hoverBeside = await pixel(place.beside);
        const hover = await evaluate(
          `(${READ})(${chip.index}, ${JSON.stringify(chip.path)}, ${JSON.stringify(place.middle)})`,
        );
        if (rest === null || hover === null) {
          continue;
        }
        const kind = hover.kind;
        if (process.env.CHIP_DEBUG) {
          process.stderr.write(
            `chip ${where}: ${JSON.stringify({ kind, control: hover.control, cursor: hover.cursor, rest: restGround, hover: hoverGround, beside: hoverBeside, ink: hover.ink, underlined: [rest.underlined, hover.underlined], selected: hover.selected })}\n`,
          );
        }
        kinds[kind] = (kinds[kind] ?? 0) + 1;
        if (!seen[name]) {
          seen[name] = new Set();
        }
        seen[name].add(`${kind} ${chip.what}`);
        const clickable = ["self", "content", "overlay"].includes(kind) && !hover.disabled;
        let focus = null;
        if (clickable) {
          const nodeId = await nodeOf(`[data-chip-control="${chip.index}"]`);
          await send("CSS.forcePseudoState", {
            nodeId,
            forcedPseudoClasses: ["focus", "focus-visible", "hover"],
          });
          await settle();
          focus = await evaluate(
            `(${READ})(${chip.index}, ${JSON.stringify(chip.path)}, ${JSON.stringify(place.middle)})`,
          );
          await send("CSS.forcePseudoState", { nodeId, forcedPseudoClasses: [] });
        }
        await away();
        const said = JSON.stringify({
          rest: rest.underlined,
          hover: hover.underlined,
          focus: focus?.underlined,
        });
        check(
          `${where}: nothing between its text and its control is underlined`,
          [rest, hover, focus].every((read) => read === null || read.underlined.length === 0),
          said,
        );
        if (clickable) {
          check(
            `${where}: a clickable chip (${kind}, ${hover.control}) shows the pointer`,
            hover.cursor === "pointer",
            String(hover.cursor),
          );
          if (!hover.selected) {
            // Its own ground, not only its row's: a chip with no ground of its own at rest whose
            // ground under the pointer is the row's says nothing about the chip.
            const own = differs(restGround, restBeside) || differs(hoverGround, hoverBeside);
            check(
              `${where}: a clickable chip (${kind}, ${hover.control}) paints another ground under the pointer`,
              differs(restGround, hoverGround) && own,
              JSON.stringify({
                rest: restGround,
                hover: hoverGround,
                beside: [restBeside, hoverBeside],
              }),
            );
          }
          if (hover.shape.layered) {
            check(
              `${where}: its hover layer stays inside the chip's shape`,
              hover.shape.clips || hover.shape.layerCorners === hover.shape.corners,
              JSON.stringify(hover.shape),
            );
          }
          // A selected chip keeps its selected look under the pointer, which this rule does
          // not set (docs/design-system.md, "Choosing Among Values").
          if (!hover.selected) {
            const ratio = contrast(hover.ink.slice(0, 3), hoverGround);
            check(
              `${where}: its text reads at ${TEXT_CONTRAST}:1 on the ground under the pointer`,
              ratio >= TEXT_CONTRAST,
              `${ratio.toFixed(2)}:1, ink ${hover.ink} on ${hoverGround}`,
            );
          }
          check(
            `${where}: its control draws the one focus ring`,
            Boolean(
              focus?.rings.some(
                (each) =>
                  each.style === ring.style &&
                  each.width === ring.width &&
                  each.color === ring.color,
              ),
            ),
            JSON.stringify({ rings: focus?.rings, ring }),
          );
        } else if (kind === "static" || hover.disabled) {
          check(
            `${where}: a static chip paints the same ground under the pointer`,
            !differs(restGround, hoverGround),
            JSON.stringify({ rest: restGround, hover: hoverGround }),
          );
          check(
            `${where}: a static chip shows no pointer`,
            hover.cursor !== "pointer",
            String(hover.cursor),
          );
        }
      }
      phase(`${name} ${theme}: ${JSON.stringify(kinds)}`);
    };

    const ready = async (condition) => {
      await waitFor(`document.readyState === "complete" && (${condition})`, STEP_MS);
      await evaluate(`document.fonts.ready.then(() => true)`);
      await settle();
    };
    const open = async (url, condition) => {
      await send("Page.navigate", { url });
      await ready(condition);
    };
    const press = async (selector, condition) => {
      await click(selector);
      await ready(condition);
    };

    // The stand-in's records of the stack's members, which a stack's page reads from the
    // cache, as a reader has them once they have opened the stack's pull requests.
    for (const number of [8, 10]) {
      await open(
        `${githubBase}/pull/${number}`,
        `document.querySelector(".github-pull-title-text") !== null`,
      );
    }
    await waitFor(
      `fetch("/api/plugin/github/stack?number=70", {cache: "no-store"}).then((r) => r.json()).then((a) => a.state === "current")`,
      STEP_MS,
    );
    phase("stack members read");

    // Each surface: how to reach it from the one before, and the scope its chips are in.
    const SURFACES = [
      {
        // A pull request's page: its header's state, readiness, labels, and branches.
        name: "the pull request's header",
        scope: ".github-pull-header",
        go: () =>
          open(
            `${githubBase}/pull/7`,
            `document.querySelector(".github-pull-readiness-link .github-pull-badge") !== null && document.querySelector(".github-pull-label") !== null`,
          ),
      },
      {
        // Its Checks tab: the Merge status section, and each check's badge and Required tag.
        name: "the Checks tab",
        scope: ".github-pull",
        go: () =>
          press(
            '.github-pull .tab-bar a[href$="/checks"]',
            `document.querySelector(".github-pull-merge-status .github-pull-requirements") !== null && document.querySelector(".github-pull-checks .github-pull-required") !== null`,
          ),
      },
      {
        // Its Changes tab: the diff toolbar's chip groups.
        name: "the Changes tab",
        scope: ".github-pull",
        go: () =>
          press(
            '.github-pull .tab-bar a[href$="/files"]',
            `document.querySelector(".github-pull .chip-group .chip") !== null`,
          ),
      },
      {
        name: "the Pulls tab",
        scope: "#tab-pulls",
        go: () =>
          press(
            '.nav-tab-bar [data-tab="pulls"]',
            `document.querySelector("#tab-pulls .github-pulls-row") !== null`,
          ),
      },
      {
        // A stack's page: its tally of states and its members' labels.
        name: "a stack's page",
        scope: ".github-pull-stack-page",
        go: () =>
          open(
            `${githubBase}/stack/70`,
            `document.querySelector(".github-pull-stack-page .github-pull-stack-tally .github-pull-badge") !== null`,
          ),
      },
      {
        // The folder, a checkout: the Files tab's revision row and its filter bar's chips.
        name: "the Files tab",
        scope: "#source-ref-selector, #nav-filter-bar",
        go: () =>
          open(
            `${folderBase}/view/`,
            `document.querySelector("#source-ref-selector .git-ref") !== null && document.querySelector("#nav-filter-bar .chip") !== null`,
          ),
      },
      {
        // The revision chooser, open: its branches' and tags' chips, each its own menu, and the
        // "checked out" tag.
        name: "the revision chooser",
        scope: "#source-ref-selector",
        go: () =>
          press(
            "#source-ref-selector .source-ref-selector-toggle",
            `document.querySelector("#source-ref-selector .source-ref-selector-kinds .chip") !== null && getComputedStyle(document.querySelector("#source-ref-selector .source-ref-selector-panel")).display !== "none"`,
          ),
      },
      {
        // The Commits tab: a history row's ref chips, each with its menu laid over it.
        name: "the Commits tab",
        scope: "#tab-git",
        go: () =>
          press(
            '.nav-tab-bar [data-tab="git"]',
            `document.querySelector("#tab-git .git-ref") !== null`,
          ),
      },
      {
        // A commit's page from a row with refs: its summary's ref chips, each its own menu.
        name: "a commit's page",
        scope: ".git-commit-view",
        go: async () => {
          await evaluate(
            `document.querySelector("#tab-git .git-ref").closest(".git-graph-row").querySelector(".git-graph-subject").click()`,
          );
          await ready(`document.querySelector(".git-commit-view .git-ref") !== null`);
        },
      },
      {
        // The folder: a table whose rows reference another's.
        name: "a table's references",
        scope: ".table-view",
        go: () =>
          open(
            `${folderBase}/view/shop.sqlite/orders`,
            `document.querySelector(".table-view .table-ref") !== null`,
          ),
      },
      {
        // The table filtered by a value: the filter's chip, and the control that removes it.
        name: "a filtered table",
        scope: ".table-view",
        go: () =>
          open(
            `${folderBase}/view/shop.sqlite/orders?f.item=eq:pen`,
            `document.querySelector(".table-view .table-chip") !== null`,
          ),
      },
      {
        // A document's images the page does not load: chips in a link, a badge's and its own.
        name: "a document's image chips",
        scope: "#preview-pane",
        go: () =>
          open(
            `${folderBase}/view/badges.md`,
            `document.querySelector(".mb-image-fallback") !== null`,
          ),
      },
      {
        // A compressed file's header badge.
        name: "a compressed file's header",
        scope: "#preview-pane",
        go: () =>
          open(
            `${folderBase}/view/notes.txt.gz`,
            `document.querySelector(".file-header-badge") !== null`,
          ),
      },
    ];
    for (const theme of onlyTheme ? [onlyTheme] : ["light", "dark"]) {
      await send("Emulation.setEmulatedMedia", {
        features: [{ name: "prefers-color-scheme", value: theme }],
      });
      for (const surface of SURFACES) {
        try {
          await surface.go();
          await audit(surface.name, theme, surface.scope);
        } catch (error) {
          check(
            `${surface.name} (${theme}): the surface is reached and read`,
            false,
            String(error),
          );
        }
      }
    }
  } finally {
    await chrome?.close();
    await folder.stop();
  }
  // Each family the design system names was found where it is drawn, so no surface's audit
  // passed by finding nothing.
  const found = (name, pattern) => [...(seen[name] ?? [])].some((each) => pattern.test(each));
  for (const [name, pattern] of [
    ["the pull request's header", /^content .*\.github-pull-readiness/],
    ["the pull request's header", /^static .*\.github-pull-label/],
    ["the pull request's header", /^static .*\.github-pull-state/],
    ["the pull request's header", /^self button\.git-ref/],
    ["the Checks tab", /^static .*\.github-pull-requirement/],
    ["the Checks tab", /^static .*\.github-pull-required/],
    ["the Changes tab", /^self button\.chip/],
    ["a stack's page", /^static .*\.github-pull-badge/],
    ["the Commits tab", /^overlay .*\.git-ref/],
    ["a commit's page", /^self button\.git-ref/],
    ["the Files tab", /^self button\.chip/],
    ["a table's references", /^self a\.table-ref/],
    ["a filtered table", /^static span\.table-chip/],
    ["the revision chooser", /^self button\.chip/],
    ["a document's image chips", /^content span\.mb-image-fallback/],
    ["a compressed file's header", /^static span\.file-header-badge/],
  ]) {
    check(
      `${name}: a chip matching ${pattern} was checked`,
      found(name, pattern),
      JSON.stringify([...(seen[name] ?? [])]),
    );
  }
  process.stderr.write(
    `${JSON.stringify(Object.fromEntries(Object.entries(seen).map(([name, kinds]) => [name, [...kinds]])), null, 1)}\n`,
  );
  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.stdout.write(`chips in Chrome: ${failures.length} of ${checks} checks failed\n`);
    process.exit(1);
  }
  process.stdout.write(`chips in Chrome: ${checks} checks passed\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
