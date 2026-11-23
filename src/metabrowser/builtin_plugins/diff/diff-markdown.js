// The Rendered layer of a comparison whose server names a route for it, as a pull
// request's does: Markdown as rendered blocks, with its front matter as the Document
// view's Frontmatter disclosure, and YAML and JSON as the structured plugin's tree
// (diff-structured.js). Source stays hydrated by the diff's existing scheduler, so a
// refusal or a reader's Source selection has a patch ready. This module names no route:
// the comparison carries the rendered route and the image route its images load from.
//
// Every changed file of a rendered format has the Rendered | Source chooser, whatever its
// size and whatever the server answers. Where Rendered cannot be shown the file shows
// Source, and its Rendered chip stays in place, unavailable, and says why (`REFUSALS`).

import { isStructuredProjection, mountStructuredDiff } from "./diff-structured.js";

const CONTEXT_BLOCKS = 2;
// The formats a changed file renders as, by its extension, as the server's route admits
// them (github/pull_rendered_diff.py), each with the name its chooser and progress use.
// An extension follows at least one character of its name, as Python's `Path.suffix`
// reads it, so a dotfile named `.json` has none.
/** @type {ReadonlyArray<[RegExp, RenderedFormat, string]>} */
const FORMATS = [
  [/[^/]\.(?:md|markdown|mdown|mkd)$/i, "markdown", "Markdown"],
  [/[^/]\.ya?ml$/i, "yaml", "YAML"],
  [/[^/]\.json$/i, "json", "JSON"],
];
// How far below the viewport a projection is requested: one viewport. A projection
// answers in 12 ms at the median and 31-33 ms at p90 of server CPU (434 real pairs), plus
// the round trip, and one `git diff` serves sixteen files. In headless Chrome, the
// production client against a simulated one-slot server (420 px files in a 900 px pane;
// earlier client in adjacent runs): at 3,000 px/s and 70 ms answers only the first
// screen's 3 of 60 files swapped from Source to Rendered in view, as before; at
// 10,000 px/s, 10-11 of 100 swapped against 51, and none was left in Source by a refusal
// against 32; at 10,000 px/s and 35 ms answers, 3 swapped against 96.
const LOOKAHEAD = "100%";
// A refused request (429: the server's one projection slot is busy, often with a load
// the reader has already scrolled past) is asked again after this, doubling to the cap.
const RETRY_MS = 100;
const RETRY_MAX_MS = 1600;
// The app's --loading-state-delay: until it passes, a Markdown file on screen at mount
// waits for its projection with Source hidden, so a ready answer paints Rendered first
// and never replaces Source in view. Past it, Source shows and Rendered replaces it.
const LOADING_DELAY_MS = 50;
// Why a file's Rendered is unavailable, by the `reason` the server's refusal names
// (`MarkdownRefusal` in diff/markdown_projection.py, `StructuredRefusal` in
// diff/structured_projection.py) and, where it names none, by its `status`. Each is the
// Rendered chip's tooltip and the end of its accessible name.
/** @type {Readonly<Record<string, string>>} */
const REFUSALS = {
  no_changes: "This file's content did not change.",
  footnotes: "Rendered cannot show a file with footnotes.",
  nesting: "This file is nested too deeply to show rendered.",
  deadline: "Rendering this file took too long, so it was stopped. Reload to try again.",
  too_large: "This file is too large to show rendered.",
};
// A refusal that names no reason: a file the projection could not read as its format.
/** @type {Readonly<Record<RenderedFormat, string>>} */
const UNREADABLE = {
  markdown: "Rendered cannot match this file's changes to its Markdown.",
  yaml: "Rendered cannot show YAML that does not parse, or has a key twice in one mapping.",
  json: "Rendered cannot show JSON that does not parse, or has a key twice in one mapping.",
};

/** @typedef {Parameters<MetabrowserPublicSdk["loadKpressAssets"]>[0]} KpressAssetManifest */
/** @typedef {"markdown" | "yaml" | "json"} RenderedFormat */
/** @typedef {import("./diff-structured.js").TreeHelpers} TreeHelpers */
/** @typedef {{key: string, change: "context" | "removed" | "added", text: string}} FrontmatterEntry */
/** @typedef {{change: "context" | "modified" | "removed" | "added", entries: FrontmatterEntry[]}} Frontmatter */
/** @typedef {"rendered" | "source"} Mode */
/** @typedef {{kind: "context" | "removed" | "added", html: string, source_only?: boolean}} Block */
/** @typedef {{
 *   section: HTMLElement, source: HTMLElement, rendered: HTMLElement,
 *   progress: HTMLElement, progressLabel: HTMLElement,
 *   control: HTMLElement,
 *   id: string, format: RenderedFormat, mode: Mode, pending: boolean, expanded: boolean,
 *   holding: boolean, tree: {dispose: () => void} | null,
 *   retryAt: number, retries: number,
 *   folds: Map<string, () => void>,
 *   state: "idle" | "ready" | "unavailable", reason: string
 * }} FileView
 *   *reason* is why Rendered is unavailable, a sentence, while *state* says it is. */

/**
 * The format a changed file renders as, when both its sides are files of one rendered
 * format: the files that have the Rendered | Source chooser. Nothing else decides it,
 * neither a file's size nor whether its changes loaded. File kinds are admitted here,
 * and source comparisons, rendering and repository reads stay with their existing owners.
 * @param {Record<string, unknown>} change
 * @returns {RenderedFormat | null}
 */
export function renderedFormat(change) {
  /** @type {Set<RenderedFormat | null>} */
  const formats = new Set();
  for (const side of [change.old, change.new]) {
    if (side == null) {
      continue;
    }
    const entry = /** @type {{entry_type?: unknown, path?: unknown}} */ (side);
    const path = typeof entry.path === "string" ? entry.path : "";
    formats.add(
      entry.entry_type === "file"
        ? (FORMATS.find(([pattern]) => pattern.test(path))?.[1] ?? null)
        : null,
    );
  }
  const [only] = formats;
  return formats.size === 1 ? (only ?? null) : null;
}

/**
 * Whether a projection may be asked for a changed file: it has a rendered format, and
 * its changes are ones the server reads a patch for. Any other file of a rendered format
 * keeps its chooser, with Rendered unavailable for the reason its Source body gives.
 * @param {Record<string, unknown>} change
 */
export function supportsRenderedChange(change) {
  return (
    renderedFormat(change) !== null &&
    (change.availability === "ready" || change.availability === "deferred")
  );
}

/**
 * Why the server refused a file's projection, as the sentence its Rendered chip says.
 * @param {unknown} answer The route's answer, which is not a projection to draw.
 * @param {RenderedFormat} format
 * @returns {string}
 */
export function refusalReason(answer, format) {
  const refusal = /** @type {{status?: unknown, reason?: unknown} | null} */ (
    answer !== null && typeof answer === "object" ? answer : null
  );
  const reason = refusal?.reason;
  if (typeof reason === "string" && Object.hasOwn(REFUSALS, reason)) {
    return REFUSALS[reason];
  }
  return refusal?.status === "too_large" ? REFUSALS.too_large : UNREADABLE[format];
}

/** @param {RenderedFormat} format */
function formatName(format) {
  return FORMATS.find(([, each]) => each === format)?.[2] ?? "";
}

/** @param {unknown} value @returns {value is Frontmatter} */
function isFrontmatter(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const frontmatter = /** @type {{change?: unknown, entries?: unknown}} */ (value);
  return (
    ["context", "modified", "removed", "added"].includes(String(frontmatter.change)) &&
    Array.isArray(frontmatter.entries) &&
    frontmatter.entries.every(
      (entry) =>
        entry !== null &&
        typeof entry === "object" &&
        typeof entry.key === "string" &&
        typeof entry.text === "string" &&
        ["context", "removed", "added"].includes(entry.change),
    )
  );
}

/**
 * Front matter as the Document view's Frontmatter disclosure shows it (KPress's
 * `kpress-frontmatter`), closed when nothing in it changed, as the Document view's is,
 * and open with each changed key in the change gutter otherwise. Every key and value is
 * text, set as text.
 * @param {Frontmatter} frontmatter
 * @returns {HTMLElement}
 */
export function frontmatterRow(frontmatter) {
  const whole = frontmatter.change === "added" || frontmatter.change === "removed";
  const row = document.createElement("div");
  row.className = `diff-markdown-block diff-markdown-frontmatter diff-markdown-${
    whole ? frontmatter.change : "context"
  }`;
  const details = document.createElement("details");
  details.className = "kpress-frontmatter";
  details.open = frontmatter.change !== "context";
  const heading = document.createElement("summary");
  heading.className = "disclosure-toggle";
  heading.textContent = "Frontmatter";
  const list = document.createElement("dl");
  for (const entry of frontmatter.entries) {
    const term = document.createElement("dt");
    const value = document.createElement("dd");
    value.textContent = entry.text;
    if (!whole && entry.change !== "context") {
      const label = document.createElement("span");
      label.className = "sr-only";
      label.textContent = entry.change === "added" ? "Added: " : "Removed: ";
      const key = document.createElement("span");
      key.textContent = entry.key;
      term.append(label, key);
      term.className = `diff-frontmatter-${entry.change}`;
      value.className = `diff-frontmatter-${entry.change}`;
    } else {
      term.textContent = entry.key;
    }
    list.append(term, value);
  }
  details.append(heading, list);
  if (whole) {
    const label = document.createElement("span");
    label.className = "sr-only";
    label.textContent = frontmatter.change === "added" ? "Added: " : "Removed: ";
    row.append(label);
  }
  row.append(details);
  return row;
}

/** @param {unknown} value @returns {value is {version: string, status: string, blocks: Block[], source_only: boolean, frontmatter?: Frontmatter, assets?: KpressAssetManifest}} */
function isProjection(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const answer =
    /** @type {{version?: unknown, status?: unknown, blocks?: unknown, source_only?: unknown, frontmatter?: unknown}} */ (
      value
    );
  return (
    answer.version === "markdown-diff-v1" &&
    (answer.frontmatter === undefined || isFrontmatter(answer.frontmatter)) &&
    answer.status === "ready" &&
    typeof answer.source_only === "boolean" &&
    Array.isArray(answer.blocks) &&
    answer.blocks.every(
      (block) =>
        block !== null &&
        typeof block === "object" &&
        ["context", "removed", "added"].includes(block.kind) &&
        typeof block.html === "string" &&
        (block.source_only === undefined || typeof block.source_only === "boolean"),
    )
  );
}

// A path in the Git path codec's wire form, and a `/view/` address of one with, at most,
// a fragment, which the server writes into the file's own heading anchors and spells with
// percent escapes.
const GIT_PATH = /^g1-[\w-]+(?:\/g1-[\w-]+)*$/;
const HEAD_LINK = /^\/view\/g1-[\w-]+(?:\/g1-[\w-]+)*(?:#[\w%.~-]+)?$/;

/**
 * Which addresses in a rendered block open something of this comparison, as the server
 * spelled them, before the shared sanitizer, which would drop every local one:
 *
 * - an image, on the comparison's own image route, which the server completes with the
 *   path of an image at the head in the Git path codec's wire form;
 * - a link to a file of the head, at its `/view/` address, only while *linksOpen* says
 *   the page shows that head. Anywhere else the address would open the same path at
 *   another commit, and a link that switched the pin first would let content choose what
 *   the server serves, so the link stays plain text.
 *
 * Every other local address is dropped.
 * @param {string | undefined} imageRoute The comparison's `image_route`, when it names one.
 * @param {() => boolean} linksOpen
 * @returns {(value: string, image: boolean) => boolean}
 */
export function markdownTargets(imageRoute, linksOpen) {
  const images =
    typeof imageRoute === "string" && imageRoute.startsWith("/") && imageRoute.includes("?")
      ? imageRoute
      : null;
  return (value, image) => {
    if (!image) {
      return HEAD_LINK.test(value) && linksOpen();
    }
    if (images === null || !value.startsWith(`${images}&`)) {
      return false;
    }
    const query = new URLSearchParams(value.slice(images.length + 1));
    return [...query.keys()].join() === "path" && GIT_PATH.test(query.get("path") ?? "");
  };
}

// The files a projection is asked for before the reader opens Changes: the rendered files
// among the ones the first screen shows. The page draws files in manifest order, a file
// bar and its first rows take about 420 px, and the server hydrates the first 8 files'
// patches with the comparison, so at most 4 rendered files of the first 8 are asked for.
// Each costs one projection, sent one at a time after the comparison arrives; the server
// waits for its projection process to start before it answers one of these, so none runs
// on the server's interpreter (mb-8274 review C2). A Markdown pair took 12 ms at the
// median and 31-33 ms at p90 of 434 real pairs before front matter was read, and those
// with front matter p50 14.6 and p90 31.4 ms after (811 pairs, review C4); a YAML pair
// 14 ms and 40 ms of 168; a JSON pair under 3 ms at p90, with 5.6-6.5 ms of reads where
// nothing else held the store's reader (review C5, since held for both reads). Review C1
// measured tree first screens holding Changes back longer than Markdown's; re-measuring
// these two and CHANGES_FIRST_SCREEN_MS on them is bead mb-10ip.
const FIRST_SCREEN_FILES = 8;
const FIRST_SCREEN_MARKDOWN = 4;

/**
 * The IDs of the rendered files a page asks projections for ahead of Changes.
 * @param {unknown[]} files A comparison manifest's files, in their order.
 * @returns {string[]}
 */
export function firstScreenRendered(files) {
  return files
    .slice(0, FIRST_SCREEN_FILES)
    .filter(
      (file) =>
        file !== null &&
        typeof file === "object" &&
        typeof (/** @type {{id?: unknown}} */ (file).id) === "string" &&
        supportsRenderedChange(/** @type {Record<string, unknown>} */ (file)),
    )
    .slice(0, FIRST_SCREEN_MARKDOWN)
    .map((file) => String(/** @type {{id: string}} */ (file).id));
}

/** @param {string} value */
function outsideLink(value) {
  if (!/^https?:\/\//i.test(value)) {
    return false;
  }
  try {
    return new URL(value).origin !== window.location.origin;
  } catch {
    return false;
  }
}

/**
 * The shared sanitizer discards reserved application URLs. Preserve only
 * the addresses *isTarget* keeps (`markdownTargets`) through it and discard other local targets
 * before the detached nodes can load any resource.
 * @param {string} html
 * @param {MetabrowserInertHtmlRuntime} inert
 * @param {HTMLTemplateElement} template
 * @param {Document} scratch
 * @param {(value: string, image: boolean) => boolean} isTarget
 */
export function sanitizeBlock(html, inert, template, scratch, isTarget) {
  template.innerHTML = html;
  /** @type {Map<string, string>} */
  const targets = new Map();
  for (const element of template.content.querySelectorAll("a[href], img[src]")) {
    const image = element.tagName === "IMG";
    const attribute = image ? "src" : "href";
    const value = element.getAttribute(attribute) ?? "";
    if (isTarget(value, image)) {
      const marker = `mb-markdown-target-${targets.size}`;
      targets.set(marker, value);
      element.setAttribute(attribute, marker);
    } else if (
      // An image from the web keeps its address: the sanitizer loads it or replaces it
      // as the reader has set. Any other image, and a link that goes nowhere, loses its.
      image
        ? inert.remoteImage(value, null) === null
        : !value.startsWith(`#${inert.ANCHOR_PREFIX}`) && !outsideLink(value)
    ) {
      element.removeAttribute(attribute);
    }
  }
  const prose = inert.kpressProse(
    inert.sanitizeNodes(template.content.childNodes, scratch, null),
    scratch,
  );
  for (const element of prose.querySelectorAll("a[href], img[src]")) {
    const image = element.tagName === "IMG";
    const attribute = image ? "src" : "href";
    const scoped = targets.get(element.getAttribute(attribute) ?? "");
    if (scoped !== undefined) {
      element.setAttribute(attribute, scoped);
    }
  }
  return prose;
}

/**
 * One rendered block's row: its change gutter and its screen-reader label. A block whose
 * source says more than its render shows draws nothing to say so: the Rendered | Source
 * chooser is how a reader reaches what Rendered does not show.
 * @param {Block} block
 * @param {(html: string) => Node} build
 */
function blockRow(block, build) {
  const row = document.createElement("div");
  row.className = `diff-markdown-block diff-markdown-${block.kind}`;
  if (block.kind !== "context") {
    const label = document.createElement("span");
    label.className = "sr-only";
    label.textContent = block.kind === "added" ? "Added: " : "Removed: ";
    row.append(label);
  }
  row.append(build(block.html));
  return row;
}

/**
 * Keep unchanged runs around an edit readable and fold their long interiors. A folded
 * run is built only when it opens, so a long document mounts the blocks a reader sees
 * rather than all of them (review C of #349: at p90, 80% of blocks ended inside a fold).
 * A context block whose source says more never folds. Returns, for each heading id a
 * fold holds, the function that opens it. With *unfold* nothing folds: every block is
 * drawn, for a page that shows its documents whole.
 * @param {DocumentFragment} fragment
 * @param {Block[]} blocks
 * @param {(html: string) => Node} build
 * @param {boolean} [unfold]
 * @returns {Map<string, () => void>}
 */
export function appendBlocks(fragment, blocks, build, unfold = false) {
  /** @type {Map<string, () => void>} */
  const folds = new Map();
  let index = 0;
  const foldable = (/** @type {Block} */ block) => block.kind === "context" && !block.source_only;
  while (index < blocks.length) {
    if (!foldable(blocks[index])) {
      fragment.append(blockRow(blocks[index++], build));
      continue;
    }
    const first = index;
    while (index < blocks.length && foldable(blocks[index])) {
      index += 1;
    }
    const run = blocks.slice(first, index);
    if (unfold || run.length <= 2 * CONTEXT_BLOCKS + 1) {
      fragment.append(...run.map((block) => blockRow(block, build)));
      continue;
    }
    const hidden = run.slice(CONTEXT_BLOCKS, -CONTEXT_BLOCKS);
    const details = document.createElement("details");
    details.className = "diff-markdown-context";
    const summary = document.createElement("summary");
    summary.className = "disclosure-toggle";
    summary.textContent = `${hidden.length} unchanged blocks`;
    details.append(summary);
    let mounted = false;
    const mount = () => {
      if (!mounted) {
        mounted = true;
        details.append(...hidden.map((block) => blockRow(block, build)));
      }
    };
    details.addEventListener("toggle", () => {
      if (details.open) {
        mount();
      }
    });
    const open = () => {
      mount();
      details.open = true;
    };
    for (const block of hidden) {
      for (const match of block.html.matchAll(/\sid="([^"]+)"/g)) {
        folds.set(match[1], open);
      }
    }
    fragment.append(
      ...run.slice(0, CONTEXT_BLOCKS).map((block) => blockRow(block, build)),
      details,
      ...run.slice(-CONTEXT_BLOCKS).map((block) => blockRow(block, build)),
    );
  }
  return folds;
}

/**
 * @param {KpressAssetManifest} assets
 * @returns {KpressAssetManifest}
 */
function stylesOnly(assets) {
  return {
    schema_version: "kpress-asset-manifest-v2",
    import_map: {},
    assets: assets.assets.filter(
      (asset) =>
        asset.loading === "stylesheet" &&
        // `@` begins the asset stamp segment (metabrowser.asset_stamps).
        /^\/kpress-static\/[\w./%@-]+\.css$/.test(asset.public_url ?? ""),
    ),
  };
}

/**
 * One queue for a mounted comparison, one request at a time to match the server's one
 * projection slot. An answer that arrives after its file switched to Source or left
 * the lookahead is kept for when the reader comes back to it.
 *
 * *holdMs* is how long the first screen's files wait for Rendered with Source hidden,
 * `LOADING_DELAY_MS` unless a page says otherwise. `firstScreen` settles once none of
 * them waits: each is drawn, Rendered or Source, or the wait is over. *unfold* draws every
 * unchanged run open (`appendBlocks`). A page that keeps the
 * comparison out of sight until then shows its first screen at the heights it keeps.
 * @param {{
 *   load: (fileId: string, signal: AbortSignal) => Promise<unknown>,
 *   controls: NonNullable<MetabrowserPublicSdk["filterControls"]>,
 *   ensureInert: () => Promise<MetabrowserInertHtmlRuntime | undefined>,
 *   ensureStructured?: () => Promise<TreeHelpers | undefined>,
 *   loadStyles: (assets: KpressAssetManifest) => Promise<void>,
 *   mutate: (change: () => void) => void,
 *   isTarget?: (value: string, image: boolean) => boolean,
 *   now?: () => number,
 *   later?: (callback: () => void, ms: number) => unknown,
 *   cancel?: (handle: unknown) => void,
 *   unfold?: boolean,
 *   holdMs?: number
 * }} deps
 */
export function createMarkdownViews(deps) {
  const now = deps.now ?? (() => Date.now());
  const isTarget = deps.isTarget ?? (() => false);
  const later = deps.later ?? ((callback, ms) => setTimeout(callback, ms));
  const cancel =
    deps.cancel ??
    ((handle) => clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (handle)));
  /** @type {Map<HTMLElement, FileView>} */
  const files = new Map();
  /** @type {Map<string, FileView>} */
  const controls = new Map();
  /** @type {Set<FileView>} */
  const nearby = new Set();
  /** @type {{file: FileView, controller: AbortController} | null} */
  let active = null;
  /** @type {IntersectionObserver | null} */
  let observer = null;
  /** @type {Promise<MetabrowserInertHtmlRuntime | undefined> | undefined} */
  let inertReady;
  /** @type {Promise<void> | undefined} */
  let stylesReady;
  /** @type {Promise<TreeHelpers | undefined> | undefined} */
  let structuredReady;
  let disposed = false;
  let observed = false;
  let reported = false;
  /** @type {unknown} */
  let holdTimer;
  /** @type {unknown} */
  let retryTimer;
  /** @type {(() => void) | undefined} */
  let unbind;
  let firstScreenSettled = false;
  /** @type {() => void} */
  let settleFirstScreen = () => {};
  /** @type {Promise<void>} */
  const firstScreen = new Promise((resolve) => {
    settleFirstScreen = () => {
      firstScreenSettled = true;
      resolve(undefined);
    };
  });

  // The first screen has been reported and none of its files waits for Rendered any more.
  function checkFirstScreen() {
    if (firstScreenSettled) {
      return;
    }
    if (
      disposed ||
      (reported &&
        !Array.from(files.values()).some(
          (file) =>
            file.holding &&
            file.expanded &&
            file.mode === "rendered" &&
            file.state === "idle" &&
            nearby.has(file),
        ))
    ) {
      settleFirstScreen();
    }
  }

  /** @param {FileView} file */
  function draw(file) {
    const rich = file.mode === "rendered" && file.state === "ready";
    file.source.hidden = rich || (file.holding && file.mode === "rendered" && file.expanded);
    file.rendered.hidden = !file.expanded || !rich;
    drawProgress(file);
  }

  // The chooser stays for a file that can only show Source: its Rendered chip is
  // unavailable and says why, as its tooltip and in its accessible name, which a keyboard
  // and a screen reader reach. It is `aria-disabled`, not `disabled`: a disabled button
  // takes no pointer and no focus, so nothing could say why. select() keeps it from
  // being chosen.
  /** @param {FileView} file */
  function drawControl(file) {
    const restoreFocus = file.control.contains(document.activeElement);
    const unavailable = file.state === "unavailable";
    file.control.innerHTML = deps.controls.groupHtml({
      key: file.source.id,
      label: `${formatName(file.format)} diff format`,
      layout: "joined",
      options: [
        { label: "Rendered", value: "rendered", ...(unavailable ? { tip: file.reason } : {}) },
        { label: "Source", value: "source" },
      ],
      select: "one",
      value: file.mode,
    });
    for (const chip of file.control.querySelectorAll("button[data-chip-value]")) {
      const button = /** @type {HTMLButtonElement} */ (chip);
      const mode = button.dataset.chipValue;
      button.setAttribute("aria-controls", mode === "rendered" ? file.rendered.id : file.source.id);
      if (mode === "rendered" && unavailable) {
        button.setAttribute("aria-disabled", "true");
        button.setAttribute("aria-label", `Rendered, unavailable. ${file.reason}`);
      }
      if (restoreFocus && mode === file.mode) {
        button.focus();
      }
    }
  }

  // The progress mark sits in the file bar beside the chooser, so it never moves the
  // diff, and stays invisible until the loading-state delay passes.
  /** @param {FileView} file */
  function drawProgress(file) {
    const showing = file.pending && file.expanded && file.mode === "rendered";
    file.progress.classList.toggle("mb-delayed-loading", showing);
    file.progressLabel.textContent = showing ? `Rendering ${formatName(file.format)}` : "";
  }

  /** @param {FileView} file */
  function interested(file) {
    return (
      nearby.has(file) &&
      file.expanded &&
      file.mode === "rendered" &&
      file.state === "idle" &&
      file.retryAt <= now()
    );
  }

  function release() {
    holdTimer = undefined;
    const held = Array.from(files.values()).filter((file) => file.holding);
    if (held.length > 0) {
      deps.mutate(() => {
        for (const file of held) {
          file.holding = false;
          draw(file);
        }
      });
    }
    checkFirstScreen();
  }

  function pump() {
    if (disposed || !observed) {
      return;
    }
    if (active !== null) {
      // The request in flight finishes even when its file leaves the lookahead: the
      // server finishes the work regardless (a cancelled waiter does not stop its
      // load), and one slot busy with a load nobody waits for refused the next file.
      // In review C's simulation of 100 files at 10,000 px/s that was 33 of them.
      return;
    }
    const file = Array.from(nearby).find(interested);
    if (file === undefined) {
      scheduleRetry();
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    active = { file, controller };
    void load(file, signal);
  }

  /** @param {FileView} file */
  function retryLater(file) {
    file.retryAt = now() + Math.min(RETRY_MS * 2 ** file.retries, RETRY_MAX_MS);
    file.retries += 1;
  }

  // Wake for the earliest refused file still waiting near the viewport.
  function scheduleRetry() {
    const waiting = Array.from(nearby).filter(
      (file) =>
        file.expanded && file.mode === "rendered" && file.state === "idle" && file.retryAt > now(),
    );
    if (retryTimer !== undefined || waiting.length === 0) {
      return;
    }
    const at = Math.min(...waiting.map((file) => file.retryAt));
    retryTimer = later(
      () => {
        retryTimer = undefined;
        pump();
      },
      Math.max(at - now(), 0),
    );
  }

  // The structured plugin's assets, asked for when the first YAML or JSON file is added,
  // so they load beside its first request; every load awaits this one promise, and
  // index.js asks for them too with the first screen's prefetch. They are four files,
  // preview.js, tree.js, index.js and styles.css: 37,324 bytes, 12,373 gzipped at
  // `delivery.GZIP_LEVEL` on 2026-11-18. Loaded inside the first-screen hold, as they were
  // before, the hold took a median 130 ms cold against 106 ms warm in the live app (mb-8274
  // review C1). A failure is not kept here, so the next load asks again, but the SDK
  // answers a provider that failed to load with that failure until the page is reloaded
  // ("Declared Dependencies" in docs/plugins.md).
  function ensureStructured() {
    structuredReady ??= Promise.resolve()
      .then(() => deps.ensureStructured?.())
      .catch(() => undefined);
    return structuredReady;
  }

  /** @param {FileView} file @param {AbortSignal} signal */
  async function load(file, signal) {
    let settled = false;
    try {
      file.pending = true;
      deps.mutate(() => drawProgress(file));
      const projection = await deps.load(file.id, signal);
      if (signal.aborted || disposed) {
        return;
      }
      if (file.format !== "markdown") {
        if (!isStructuredProjection(projection)) {
          fallBack(file, refusalReason(projection, file.format));
          return;
        }
        const tree = await ensureStructured();
        if (tree === undefined) {
          structuredReady = undefined;
          throw new Error("The structured tree renderer is unavailable.");
        }
        if (signal.aborted || disposed) {
          return;
        }
        settled = true;
        deps.mutate(() => {
          file.tree?.dispose();
          file.tree = mountStructuredDiff(file.rendered, projection.root, tree, {
            sourceOnly: projection.source_only,
          });
          file.state = "ready";
          file.pending = false;
          file.retries = 0;
          draw(file);
        });
        checkFirstScreen();
        return;
      }
      if (!isProjection(projection)) {
        fallBack(file, refusalReason(projection, file.format));
        return;
      }
      inertReady ??= deps.ensureInert();
      /** @type {MetabrowserInertHtmlRuntime | undefined} */
      let inert;
      try {
        inert = await inertReady;
      } catch {
        inert = undefined;
      }
      if (inert === undefined) {
        // Not kept: choosing Rendered again loads it again.
        inertReady = undefined;
        throw new Error("The untrusted Markdown sanitizer is unavailable.");
      }
      if (projection.assets !== undefined) {
        stylesReady ??= deps.loadStyles(stylesOnly(projection.assets)).catch(() => {});
        await stylesReady;
      }
      if (signal.aborted || disposed) {
        return;
      }
      const content = document.createDocumentFragment();
      if (projection.frontmatter !== undefined) {
        content.append(frontmatterRow(projection.frontmatter));
      }
      const scratch = document.implementation.createHTMLDocument("");
      const template = document.createElement("template");
      const folds = appendBlocks(
        content,
        projection.blocks,
        (html) => sanitizeBlock(html, inert, template, scratch, isTarget),
        deps.unfold === true,
      );
      settled = true;
      deps.mutate(() => {
        file.rendered.replaceChildren(content);
        file.folds = folds;
        file.state = "ready";
        file.pending = false;
        file.retries = 0;
        draw(file);
      });
      checkFirstScreen();
    } catch (error) {
      if (!signal.aborted && !disposed) {
        if (/** @type {{status?: unknown}} */ (error)?.status === 429) {
          retryLater(file);
        } else {
          console.warn("metabrowser diff: a rendered file failed; showing Source", error);
          fallBack(file, null);
        }
      }
    } finally {
      if (!settled && !disposed) {
        file.pending = false;
        deps.mutate(() => drawProgress(file));
      }
      active = null;
      pump();
    }
  }

  // Source is what a file shows when it is not rendered, and nothing in its body says
  // so. A file the server refused keeps its chooser with Rendered unavailable, for
  // *reason*; one whose request failed, with no reason, keeps Rendered to choose, which
  // asks again.
  /** @param {FileView} file @param {string | null} reason */
  function fallBack(file, reason) {
    deps.mutate(() => {
      file.state = reason === null ? "idle" : "unavailable";
      file.reason = reason ?? "";
      file.mode = "source";
      file.holding = false;
      drawControl(file);
      draw(file);
    });
    checkFirstScreen();
  }

  /** @param {FileView} file @param {Mode} mode */
  function select(file, mode) {
    if (disposed || file.mode === mode || (mode === "rendered" && file.state === "unavailable")) {
      return;
    }
    deps.mutate(() => {
      file.mode = mode;
      file.holding = false;
      if (mode === "rendered") {
        file.retryAt = 0;
      }
      drawControl(file);
      draw(file);
    });
    pump();
  }

  return {
    /**
     * @param {{
     *   section: HTMLElement, bar: HTMLElement, end: HTMLElement, source: HTMLElement,
     *   id: string, format: RenderedFormat, unavailable?: string
     * }} input The file's section; its bar; the group of controls at the bar's end,
     *   which the chooser leads; its Source body; and the format it renders as
     *   (`renderedFormat`).
     *   *unavailable* is why no projection is asked for the file, a sentence, for one
     *   whose changes the page has no patch of (`supportsRenderedChange`): it shows
     *   Source, which says the same, from the start.
     */
    add({ section, bar, end, source, id, format, unavailable }) {
      const control = document.createElement("div");
      control.className = "diff-markdown-control";
      // Markdown is a KPress fragment; a tree is the structured plugin's own surface.
      const rendered = document.createElement(format === "markdown" ? "article" : "div");
      if (format === "markdown") {
        rendered.className = "kpress kpress-inert diff-markdown";
      } else {
        rendered.className = "diff-structured";
        ensureStructured();
      }
      rendered.id = `${source.id}-rendered`;
      const progress = document.createElement("span");
      progress.className = "diff-markdown-progress";
      progress.setAttribute("role", "status");
      const spinner = document.createElement("span");
      spinner.className = "spinner spinner-sm";
      spinner.setAttribute("aria-hidden", "true");
      const progressLabel = document.createElement("span");
      progressLabel.className = "sr-only";
      progress.append(spinner, progressLabel);
      /** @type {FileView} */
      const file = {
        section,
        source,
        rendered,
        progress,
        progressLabel,
        id,
        format,
        tree: null,
        control,
        mode: unavailable === undefined ? "rendered" : "source",
        expanded: true,
        pending: false,
        holding: unavailable === undefined,
        retryAt: 0,
        retries: 0,
        folds: new Map(),
        state: unavailable === undefined ? "idle" : "unavailable",
        reason: unavailable ?? "",
      };
      // A fragment link into a folded run opens that fold before the browser looks.
      rendered.addEventListener("click", (event) => {
        const origin = /** @type {{closest?: (selector: string) => Element | null}} */ (
          event.target
        );
        const href = origin?.closest?.("a[href]")?.getAttribute("href") ?? "";
        if (href.startsWith("#")) {
          file.folds.get(href.slice(1))?.();
        }
      });
      // The progress mark leads, on the side of the bar's free space, so the chooser
      // and whatever follows it stay where they are when it appears.
      bar.classList.add("diff-file-bar-markdown");
      end.prepend(progress, control);
      source.before(rendered);
      files.set(section, file);
      controls.set(source.id, file);
      drawControl(file);
      draw(file);
      return {
        /** @param {boolean} expanded */
        setExpanded(expanded) {
          file.expanded = expanded;
          draw(file);
          pump();
        },
      };
    },
    /** @param {HTMLElement} container @param {Element | null} root */
    observe(container, root) {
      observed = true;
      if (files.size === 0) {
        settleFirstScreen();
        return;
      }
      holdTimer = later(release, deps.holdMs ?? LOADING_DELAY_MS);
      unbind = deps.controls.bind(container, {
        onChange(key, value, selectType) {
          const file = controls.get(key);
          if (
            file !== undefined &&
            selectType === "one" &&
            (value === "source" || value === "rendered")
          ) {
            // The shared handler moves focus first. Repaint once that handler
            // returns so its focus recovery cannot find another file's chips.
            queueMicrotask(() => select(file, value));
          }
        },
      });
      observer = new IntersectionObserver(
        (entries) => {
          if (disposed) {
            return;
          }
          /** @type {FileView[]} */
          const away = [];
          for (const entry of entries) {
            const file = files.get(/** @type {HTMLElement} */ (entry.target));
            if (file !== undefined) {
              if (entry.isIntersecting) {
                nearby.add(file);
              } else {
                nearby.delete(file);
                if (file.holding) {
                  away.push(file);
                }
              }
            }
          }
          // Only the files near the first screen wait; the rest draw Source now.
          if (!reported) {
            reported = true;
            for (const file of files.values()) {
              if (file.holding && !nearby.has(file) && !away.includes(file)) {
                away.push(file);
              }
            }
          }
          if (away.length > 0) {
            deps.mutate(() => {
              for (const file of away) {
                file.holding = false;
                draw(file);
              }
            });
          }
          pump();
          checkFirstScreen();
        },
        { root, rootMargin: `0px 0px ${LOOKAHEAD} 0px` },
      );
      for (const section of files.keys()) {
        observer.observe(section);
      }
    },
    firstScreen,
    /**
     * Make every link to a file of the head plain text, in what is drawn: the page learned
     * that the server serves another pin, at which those addresses open other files. What
     * is drawn later asks *isTarget*, which says so itself.
     */
    closeHeadLinks() {
      for (const file of files.values()) {
        for (const link of file.rendered.querySelectorAll('a[href^="/view/"]')) {
          link.removeAttribute("href");
        }
      }
    },
    dispose() {
      disposed = true;
      settleFirstScreen();
      observer?.disconnect();
      active?.controller.abort();
      if (active !== null) {
        active.file.progress.classList.remove("mb-delayed-loading");
      }
      for (const handle of [holdTimer, retryTimer]) {
        if (handle !== undefined) {
          cancel(handle);
        }
      }
      unbind?.();
      unbind = undefined;
      for (const file of files.values()) {
        file.tree?.dispose();
        file.tree = null;
      }
      files.clear();
      controls.clear();
      nearby.clear();
    },
  };
}
