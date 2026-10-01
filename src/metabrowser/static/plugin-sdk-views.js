// View-phase code: what a view's renderer calls, and the first tree does not.
//
// plugin-sdk.js is a startup script, so every byte of it is fetched before the first
// tree paints. Two things are here instead, in one file because nothing uses either
// without the other: a Source view's line gutter and `#L` anchors
// (`window.MetabrowserSourceLineAnchors`), and the SDK helpers that build a view's
// markup -- the Source surface, the copy wrapper, the partial-content notice -- with
// the syntax service, since nothing asks for a token until a view shows code.
//
// It is the `sdk-views` on-demand bundle. `loadViewComposition` fetches it beside the
// view compositor, and plugin-sdk.js (`loadPluginsForKind`) fetches it before it
// evaluates any plugin's code on a path that has no compositor, such as the commit
// page's or the pull-request page's. So every helper is on `window.metabrowser`
// wherever a plugin's code can run: while its module evaluates, in any hook, in any
// handler. A plugin sees the same SDK it always did.
//
// That wait is on the plugin's code, not on its transfer: the loader starts the
// plugin's stylesheets and preloads its module beside this file, so a plugin loaded
// without the compositor takes no round trip more than when these helpers were part of
// a startup script. When this file cannot be fetched the load is refused, no plugin's
// code has run, and the caller says so; a plugin whose own assets fail is logged and
// skipped, as it always was.
//
// Measured 2026-10-01 in Chrome 152: the helpers were 5,632 of plugin-sdk.js's 22,308
// compressed bytes as a startup script, and the gutter's module 7,692 more as a
// startup script of its own. As two bundles they were two requests beside the
// compositor's, on a pool of six connections the tree and the prefetched syntax
// library also use, and a plugin loaded without the compositor got one of them and
// not the other. See explorations/performance-loop/experiments/exp-037.

// ── Line numbers and line anchors ─────────────────────────────────────────────
//
// A source view shows a gutter of line numbers beside its code. A `/view/` address
// whose fragment is `#L10`, `#L10-L20`, or `#L10C5-L20C8` highlights those lines, and
// scrolls the first one into view once the file is open and whenever the fragment
// changes. Clicking a line number anchors that line, and shift-clicking extends the
// anchor to a range; either replaces the address through the navigation controller,
// so the address bar, and a copy of it, carries the anchor. Columns are kept in the
// address but highlight whole lines. An address that anchors lines, or carries
// GitHub's `plain=1`, opens a file in its Source view (`preferredView`).
//
// The gutter is also a keyboard control, a vertical slider over the lines: Tab
// reaches it, the arrow keys, Page Up, Page Down, Home, and End move the anchor, and
// Shift with any of them extends it to a range. Its value is the anchored range in
// words, which a screen reader announces as the anchor moves; an anchor set any other
// way is announced by a visually hidden status line.
//
// The fragment is the only state: `describe` turns it and what the view has loaded
// into what to highlight and what to say, and `nextFragment` and `keyStep` turn a
// click or a key into the next fragment. None touches the DOM. A view may show its
// text in several code blocks under one gutter, such as a Markdown file's front
// matter and its body; each block's highlight is offset by the lines above it.
// CSS paints the highlight from the anchored
// lines and the measured height of one line, which is the gutter's height over its
// line count: rendered line boxes are rounded, so a position computed in `lh` units
// drifts off its line far down a large file. A large file shows only its first part
// until Load more; a line past that part is reported as not loaded rather than guessed
// at, and becomes the anchor, scrolled to, once Load more reaches it. A view mounted
// when its tab is first shown scrolls to the anchor at once; a view the shell renders
// into its inert stage waits for the fragment event the shell delivers once the view
// is in the pane.
//
// tests/dom/source-line-anchors-session.js runs these functions, and the DOM glue
// against a small fake document, from the command line.

((global) => {
  // The same grammar as the GitHub reducer's `_LINE_ANCHOR` in
  // builtin_plugins/github/urls.py: lines and columns from 1, at most nine digits.
  const ANCHOR =
    /^L([1-9][0-9]{0,8})(?:C([1-9][0-9]{0,8}))?(?:-L([1-9][0-9]{0,8})(?:C([1-9][0-9]{0,8}))?)?$/;

  /**
   * @typedef {Readonly<{start: number, end: number}>} LineRange
   * @typedef {Readonly<{lines: number, truncated: boolean}>} LoadedText
   * @typedef {Readonly<{
   *   status: "none" | "shown" | "partial" | "not-loaded" | "past-end",
   *   start: number,
   *   end: number,
   *   message: string,
   * }>} AnchorState
   * @typedef {Readonly<{path: string, query?: string, fragment?: string}>} Target
   * @typedef {Readonly<{
   *   current(): Target | null,
   *   open(target: Target, options: {replace: boolean}): Promise<void>,
   * }>} Navigation
   * @typedef {{
   *   pre: HTMLElement,
   *   gutter: HTMLElement,
   *   notice: HTMLElement | null,
   *   status: HTMLElement,
   *   statusText: string,
   *   statusLive: boolean,
   *   target: HTMLElement | null,
   *   path: string,
   *   loaded: LoadedText,
   *   navigation: Navigation | null,
   *   applied: string,
   *   chosen: string,
   *   focus: number,
   *   state: AnchorState,
   *   observer: ResizeObserver | null,
   * }} View
   */

  /**
   * The lines a fragment anchors, in order, or null for any other fragment.
   *
   * @param {string | null | undefined} fragment
   * @returns {LineRange | null}
   */
  function parse(fragment) {
    const match = ANCHOR.exec(typeof fragment === "string" ? fragment : "");
    if (!match) {
      return null;
    }
    const first = Number(match[1]);
    const last = match[3] ? Number(match[3]) : first;
    return Object.freeze({ start: Math.min(first, last), end: Math.max(first, last) });
  }

  /**
   * Lines in a text as a source view shows them: a final newline ends the last line
   * rather than starting another, and a partial last line still counts.
   *
   * @param {string} text
   */
  function countLines(text) {
    if (!text) {
      return 0;
    }
    let lines = 0;
    let index = text.indexOf("\n");
    while (index !== -1) {
      lines += 1;
      index = text.indexOf("\n", index + 1);
    }
    return text.endsWith("\n") ? lines : lines + 1;
  }

  /** @param {number} lines */
  function gutterText(lines) {
    const numbers = new Array(lines);
    for (let line = 0; line < lines; line++) {
      numbers[line] = line + 1;
    }
    return numbers.join("\n");
  }

  /** @param {number} value */
  function grouped(value) {
    return value.toLocaleString("en-US");
  }

  /**
   * What a fragment highlights in a view that has loaded some lines of its file.
   *
   * @param {string | null | undefined} fragment
   * @param {LoadedText} loaded
   * @returns {AnchorState}
   */
  function describe(fragment, loaded) {
    const range = parse(fragment);
    if (!range) {
      return Object.freeze({ status: "none", start: 0, end: 0, message: "" });
    }
    const { start, end } = range;
    const lines = Math.max(0, loaded.lines);
    const single = start === end;
    const asked = single ? `Line ${grouped(start)}` : `Lines ${grouped(start)}–${grouped(end)}`;
    const loadedPart = lines === 1 ? "line 1" : `lines 1–${grouped(lines)}`;
    if (start > lines && loaded.truncated) {
      const message =
        `${asked} ${single ? "is" : "are"} past the part of this file loaded so far ` +
        `(${loadedPart}). Load more to reach ${single ? "it" : "them"}.`;
      return Object.freeze({ status: "not-loaded", start, end, message });
    }
    if (start > lines) {
      const fileLines = lines === 1 ? "1 line" : `${grouped(lines)} lines`;
      const message = `${asked} ${single ? "is" : "are"} past the end of this file, which has ${fileLines}.`;
      return Object.freeze({ status: "past-end", start, end, message });
    }
    if (end > lines) {
      const message = loaded.truncated
        ? `${asked} continue past the part of this file loaded so far (${loadedPart}). Load more to see the rest.`
        : `${asked} run past the end of this file, which ends at line ${grouped(lines)}.`;
      return Object.freeze({ status: "partial", start, end: lines, message });
    }
    return Object.freeze({ status: "shown", start, end, message: "" });
  }

  /**
   * The fragment a click on a line number sets. A plain click anchors the line; a
   * shift-click extends from the current anchor's first line to the clicked one.
   *
   * @param {string | null | undefined} current
   * @param {number} line
   * @param {boolean} extend
   */
  function nextFragment(current, line, extend) {
    const range = extend ? parse(current) : null;
    if (!range || range.start === line) {
      return `L${line}`;
    }
    const first = Math.min(range.start, line);
    const last = Math.max(range.start, line);
    return `L${first}-L${last}`;
  }

  /**
   * The anchor a key on the focused gutter sets, and the line the key moved: Up and
   * Down move one line, Page Up and Page Down a page, Home and End to the first and
   * last loaded line. With Shift the key moves only the range's moving end, `focus`,
   * and keeps the other end; without it the anchor becomes the one line moved to.
   * With nothing anchored, a key starts from `origin`, the first line in view.
   *
   * @param {string | null | undefined} current
   * @param {number} focus The moving end of the current range, or 0 for its last line.
   * @param {string} key
   * @param {boolean} extend
   * @param {Readonly<{lines: number, page: number, origin: number}>} layout
   * @returns {Readonly<{fragment: string, focus: number}> | null} Null for any other key.
   */
  function keyStep(current, focus, key, extend, layout) {
    const lines = Math.max(0, layout.lines);
    if (lines < 1) {
      return null;
    }
    const range = parse(current);
    const page = Math.max(1, layout.page);
    const from = range
      ? focus === range.start || focus === range.end
        ? focus
        : range.end
      : Math.min(lines, Math.max(1, layout.origin));
    // With nothing anchored, the first move anchors the line it starts from.
    const step = range ? 1 : 0;
    /** @type {Record<string, number>} */
    const moves = {
      ArrowDown: from + step,
      ArrowUp: from - step,
      PageDown: from + page,
      PageUp: from - page,
      Home: 1,
      End: lines,
    };
    if (!Object.hasOwn(moves, key)) {
      return null;
    }
    const line = Math.min(lines, Math.max(1, moves[key]));
    if (!extend || !range) {
      return Object.freeze({ fragment: `L${line}`, focus: line });
    }
    const fixed = from === range.start ? range.end : range.start;
    const first = Math.min(fixed, line);
    const last = Math.max(fixed, line);
    const fragment = first === last ? `L${first}` : `L${first}-L${last}`;
    return Object.freeze({ fragment, focus: line });
  }

  /**
   * The highlighted lines in words, as the gutter's value and the status line say them.
   *
   * @param {AnchorState} state
   */
  function spoken(state) {
    if (state.status !== "shown" && state.status !== "partial") {
      return "No line anchored";
    }
    return state.start === state.end
      ? `Line ${grouped(state.start)}`
      : `Lines ${grouped(state.start)}–${grouped(state.end)}`;
  }

  /**
   * The view an address asks a file to open in: its Source view when the address
   * anchors lines or carries GitHub's `plain=1`, which on github.com shows a rendered
   * file's source. `plain=1` is the same test as `_plain` in the GitHub reducer
   * (builtin_plugins/github/urls.py). Null leaves the choice to the file's views.
   *
   * @param {Target | null | undefined} target
   * @returns {"source" | null}
   */
  function preferredView(target) {
    if (!target) {
      return null;
    }
    const plain = (target.query || "").split("&").includes("plain=1");
    return plain || parse(target.fragment) ? "source" : null;
  }

  /**
   * The line under a point in the gutter, from its offset below the gutter's top.
   *
   * @param {number} offsetY
   * @param {number} lineHeight
   * @param {number} lines
   */
  function lineAt(offsetY, lineHeight, lines) {
    if (!(lineHeight > 0) || lines < 1) {
      return 0;
    }
    return Math.min(lines, Math.max(1, Math.floor(offsetY / lineHeight) + 1));
  }

  /**
   * The gutter's markup for a source view's text: one number per line, as one text
   * node. It is a slider over the lines, whose children assistive technology does not
   * read, because the code already has the lines; `mount` sets its value.
   *
   * @param {string} text
   */
  function gutterHtml(text) {
    const lines = countLines(text);
    return (
      '<span class="source-line-numbers" role="slider" tabindex="0" aria-label="Line numbers" ' +
      `aria-orientation="vertical" aria-valuemin="1" aria-valuemax="${Math.max(1, lines)}" ` +
      `aria-valuenow="1" aria-valuetext="No line anchored">${gutterText(lines)}</span>`
    );
  }

  // ── DOM glue ──────────────────────────────────────────────────────────────

  /** @type {Set<View>} */
  const views = new Set();

  // The anchor a view could not show because Load more had not reached it. Load more
  // either appends to the view or renders it again; either way `refresh` follows and
  // scrolls to the anchor once it is there. One file is shown at a time, so one slot.
  /** @type {{path: string, fragment: string} | null} */
  let awaiting = null;

  /** @param {string} path */
  function filePath(path) {
    return path.endsWith("/") ? path.slice(0, -1) : path;
  }

  /**
   * The code blocks under a view's gutter, in order.
   *
   * @param {HTMLElement} pre
   * @returns {HTMLElement[]}
   */
  function codeParts(pre) {
    return /** @type {HTMLElement[]} */ (
      Array.from(pre.childNodes).filter(
        (node) => node.nodeType === 1 && /** @type {Element} */ (node).tagName === "CODE",
      )
    );
  }

  /**
   * Count the lines a view shows, and offset each code block's highlight by the lines
   * in the blocks above it. Each block starts on a line of its own.
   *
   * @param {HTMLElement} pre
   */
  function layoutParts(pre) {
    const parts = codeParts(pre);
    let lines = 0;
    for (const code of parts) {
      if (parts.length > 1) {
        code.style.setProperty("--mb-line-offset", String(lines));
      }
      lines += countLines(code.textContent || "");
    }
    if (parts.length > 1) {
      pre.style.setProperty("--mb-source-parts", String(parts.length));
    }
    return lines;
  }

  /** @param {View} view */
  function currentTarget(view) {
    try {
      const target = view.navigation?.current() ?? null;
      return target && filePath(target.path) === filePath(view.path) ? target : null;
    } catch (_error) {
      // Navigation is not attached yet; the fragment event after the open applies it.
      return null;
    }
  }

  // A view leaves the registry once its container has been replaced. The shell
  // renders into a connected stage and moves the nodes into the pane, so a view is
  // connected from mount until its file is closed.
  function prune() {
    for (const view of views) {
      if (!view.pre.isConnected) {
        view.observer?.disconnect();
        views.delete(view);
      }
    }
  }

  /** @param {View} view */
  function paintNotice(view) {
    if (!view.state.message) {
      view.notice?.remove();
      view.notice = null;
      return;
    }
    if (!view.notice) {
      const notice = view.pre.ownerDocument.createElement("div");
      notice.className = "notice metabrowser-source-anchor-notice";
      notice.setAttribute("role", "status");
      (view.pre.closest(".content-copy-wrap") ?? view.pre).before(notice);
      view.notice = notice;
    }
    view.notice.textContent = view.state.message;
  }

  /**
   * The rendered height of one line. The gutter is one text node of the code's line
   * boxes, so its height over its line count is exact where `1lh` is not: at 110% zoom
   * a band placed in `lh` units is 32 lines off by line 40,000.
   *
   * @param {View} view
   */
  function linePitch(view) {
    const height = view.gutter.getBoundingClientRect().height;
    return view.loaded.lines > 0 && height > 0 ? height / view.loaded.lines : 0;
  }

  /** @param {View} view */
  function measure(view) {
    const pitch = linePitch(view);
    if (pitch > 0) {
      view.pre.style.setProperty("--mb-line-pitch", `${pitch}px`);
    }
  }

  /** @param {View} view */
  function reveal(view) {
    view.pre.style.removeProperty("--mb-line-focus");
    view.target?.scrollIntoView({ block: "center", inline: "nearest" });
  }

  /**
   * The gutter's value, and the status line, which is empty while the gutter has focus
   * because a screen reader announces the focused gutter's own value as it changes.
   *
   * @param {View} view
   */
  function paintValue(view) {
    const { status, start, end } = view.state;
    const lit = status === "shown" || status === "partial";
    const moving = lit && view.focus >= start && view.focus <= end ? view.focus : start;
    view.gutter.setAttribute("aria-valuemax", String(Math.max(1, view.loaded.lines)));
    view.gutter.setAttribute("aria-valuenow", String(lit ? moving : 1));
    view.gutter.setAttribute("aria-valuetext", spoken(view.state));
    const focused = view.pre.ownerDocument.activeElement === view.gutter;
    view.statusText = lit && !focused ? `${spoken(view.state)} highlighted.` : "";
    if (view.statusLive) {
      view.status.textContent = view.statusText;
    }
  }

  /** @param {View} view */
  function paintHighlight(view) {
    const { status, start, end } = view.state;
    const lit = status === "shown" || status === "partial";
    view.pre.classList.toggle("has-line-anchor", lit);
    if (!lit) {
      view.pre.style.removeProperty("--mb-line-first");
      view.pre.style.removeProperty("--mb-line-last");
      view.target?.remove();
      view.target = null;
      return;
    }
    view.pre.style.setProperty("--mb-line-first", String(start));
    view.pre.style.setProperty("--mb-line-last", String(end));
    if (!view.target) {
      const target = view.pre.ownerDocument.createElement("span");
      target.className = "source-line-anchor-target";
      view.gutter.appendChild(target);
      view.target = target;
    }
    measure(view);
  }

  /**
   * Show a fragment in a view: the highlight and the notice follow it, and the first
   * anchored line scrolls into view when asked.
   *
   * @param {View} view
   * @param {string} fragment
   * @param {boolean} scroll
   */
  function apply(view, fragment, scroll) {
    view.applied = fragment;
    view.state = describe(fragment, view.loaded);
    if (view.state.status === "not-loaded") {
      awaiting = { path: filePath(view.path), fragment };
    } else if (scroll && awaiting?.path === filePath(view.path)) {
      awaiting = null;
    }
    paintHighlight(view);
    paintNotice(view);
    paintValue(view);
    if (scroll) {
      reveal(view);
    }
  }

  /**
   * Anchor a fragment the reader chose on the gutter, and put it in the address
   * through the navigation controller, which then delivers it back to this view. A
   * chosen line stays where the reader is.
   *
   * @param {View} view
   * @param {string} fragment
   */
  function choose(view, fragment) {
    apply(view, fragment, false);
    const target = currentTarget(view);
    if (!target || !view.navigation) {
      return;
    }
    view.chosen = fragment;
    const next = target.query
      ? { path: target.path, query: target.query, fragment }
      : { path: target.path, fragment };
    void view.navigation.open(next, { replace: true }).catch((error) => {
      view.chosen = "";
      console.warn("Could not put the line anchor in the address", error);
    });
  }

  /**
   * @param {View} view
   * @param {MouseEvent} event
   */
  function handleGutterClick(view, event) {
    if (event.button !== 0 || event.target !== view.gutter) {
      return;
    }
    const line = lineAt(event.offsetY, linePitch(view), view.loaded.lines);
    if (!line) {
      return;
    }
    view.focus = line;
    choose(view, nextFragment(view.applied, line, event.shiftKey));
  }

  /**
   * The nearest element above a view that scrolls vertically, or null.
   *
   * @param {HTMLElement} pre
   * @returns {HTMLElement | null}
   */
  function scrollingPane(pre) {
    const frame = pre.ownerDocument.defaultView;
    for (let node = pre.parentElement; node; node = node.parentElement) {
      const overflow = frame?.getComputedStyle(node).overflowY;
      if ((overflow === "auto" || overflow === "scroll") && node.scrollHeight > node.clientHeight) {
        return node;
      }
    }
    return null;
  }

  /**
   * @param {View} view
   * @param {KeyboardEvent} event
   */
  function handleGutterKey(view, event) {
    if (event.altKey || event.ctrlKey || event.metaKey) {
      return;
    }
    // A page is what the pane that scrolls the view shows, or the window when the
    // page itself scrolls; the first line in view is the one at that pane's top.
    const pitch = linePitch(view);
    const pane = scrollingPane(view.pre);
    const height = pane ? pane.clientHeight : global.innerHeight;
    const above =
      (pane ? pane.getBoundingClientRect().top : 0) - view.gutter.getBoundingClientRect().top;
    const step = keyStep(view.applied, view.focus, event.key, event.shiftKey, {
      lines: view.loaded.lines,
      page: pitch > 0 && height > 0 ? Math.floor(height / pitch) - 1 : 1,
      origin: pitch > 0 && above > 0 ? lineAt(above, pitch, view.loaded.lines) : 1,
    });
    if (!step) {
      return;
    }
    event.preventDefault();
    view.focus = step.focus;
    choose(view, step.fragment);
    // The line the key moved to comes into view, however little the page scrolls.
    if (view.target) {
      view.pre.style.setProperty("--mb-line-focus", String(step.focus));
      view.target.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  }

  /**
   * Wire line anchors into a source view just rendered into `host`, and paint the
   * current address's anchor. Scrolling waits for the fragment event the shell
   * delivers once the view is in the pane.
   *
   * @param {ParentNode} host
   * @param {{path: string, truncated: boolean, navigation: Navigation | null}} options
   */
  function mount(host, options) {
    prune();
    const pre = /** @type {HTMLElement | null} */ (
      host.querySelector("pre.metabrowser-source-lines")
    );
    const gutter = /** @type {HTMLElement | null} */ (
      pre?.querySelector(".source-line-numbers") ?? null
    );
    if (!pre || !gutter || codeParts(pre).length === 0) {
      return;
    }
    const status = pre.ownerDocument.createElement("span");
    status.className = "visually-hidden metabrowser-source-anchor-status";
    status.setAttribute("role", "status");
    (pre.closest(".content-copy-wrap") ?? pre).before(status);
    /** @type {View} */
    const view = {
      pre,
      gutter,
      notice: null,
      status,
      statusText: "",
      statusLive: false,
      target: null,
      path: options.path,
      loaded: Object.freeze({ lines: layoutParts(pre), truncated: options.truncated }),
      navigation: options.navigation,
      applied: "",
      chosen: "",
      focus: 0,
      state: describe("", { lines: 0, truncated: false }),
      observer: null,
    };
    views.add(view);
    // A live region created and filled in one task is not announced, so the status
    // line takes its first words in a later task, and every change after that at once.
    global.setTimeout(() => {
      view.statusLive = true;
      view.status.textContent = view.statusText;
    }, 0);
    if (typeof global.ResizeObserver === "function") {
      // Zoom, a late web font, or a tab shown for the first time changes the line
      // box; measure again so the highlight stays on its lines.
      view.observer = new global.ResizeObserver(() => {
        if (view.target) {
          measure(view);
        }
      });
      view.observer.observe(gutter);
    }
    // A shift-click would otherwise extend the page's text selection to the gutter.
    gutter.addEventListener("mousedown", (event) => {
      if (event.shiftKey) {
        event.preventDefault();
      }
    });
    gutter.addEventListener("click", (event) => handleGutterClick(view, event));
    gutter.addEventListener("keydown", (event) => handleGutterKey(view, event));
    // Outside the shell's inert stage, the view is being shown now, when its tab is
    // first opened, and no fragment event will follow; scroll to the anchor at once.
    apply(view, currentTarget(view)?.fragment || "", !pre.closest("[inert]"));
  }

  /**
   * Bring the views under `root` in line with what Load more loaded, whether it
   * appended to the view or rendered it again: renumber the gutter and reapply the
   * anchor, scrolling to it if it has just been reached.
   *
   * @param {ParentNode} root
   * @param {{content_truncated?: boolean}} loaded The cache value after the append.
   */
  function refresh(root, loaded) {
    prune();
    for (const view of views) {
      if (!root.contains(view.pre)) {
        continue;
      }
      const lines = layoutParts(view.pre);
      if (lines !== view.loaded.lines) {
        const numbers = view.gutter.firstChild;
        if (numbers && numbers.nodeType === 3) {
          numbers.nodeValue = gutterText(lines);
        } else {
          view.gutter.prepend(view.pre.ownerDocument.createTextNode(gutterText(lines)));
        }
      }
      view.loaded = Object.freeze({ lines, truncated: !!loaded.content_truncated });
      const reached = awaiting?.path === filePath(view.path) && awaiting.fragment === view.applied;
      apply(view, view.applied, false);
      if (reached && view.state.status !== "not-loaded") {
        awaiting = null;
        reveal(view);
      }
    }
  }

  /** @param {Event} event */
  function handleFragment(event) {
    const detail = /** @type {CustomEvent<{target?: Target}>} */ (event).detail;
    const target = detail?.target;
    if (!target) {
      return;
    }
    prune();
    for (const view of views) {
      if (filePath(target.path) === filePath(view.path)) {
        const fragment = target.fragment || "";
        const own = fragment === view.chosen;
        view.chosen = "";
        if (!own) {
          view.focus = 0;
        }
        apply(view, fragment, !own);
      }
    }
  }

  if (typeof global.addEventListener === "function") {
    global.addEventListener("metabrowser:navigation-fragment", handleFragment);
  }

  global.MetabrowserSourceLineAnchors = Object.freeze({
    countLines,
    describe,
    gutterHtml,
    keyStep,
    lineAt,
    mount,
    nextFragment,
    parse,
    preferredView,
    refresh,
    spoken,
  });
})(/** @type {Window & typeof globalThis} */ (typeof window !== "undefined" ? window : globalThis));

// ── SDK view helpers and the syntax service ───────────────────────────────────

((global) => {
  const mb = global.metabrowser;
  if (!mb || typeof mb.registerView !== "function") {
    throw new Error("plugin-sdk-views.js requires window.metabrowser");
  }
  // Defined above, in this same script: a Source view cannot be without its gutter.
  const definedLineAnchors = global.MetabrowserSourceLineAnchors;
  if (!definedLineAnchors) {
    throw new Error("plugin-sdk-views.js did not define the line anchors");
  }
  const lineAnchors = definedLineAnchors;
  const { delegateOwnerAttribute, escapeHtml, formatSize } = mb;

  const HIGHLIGHT_TOKEN_CLASS_RE = /^[A-Za-z_][A-Za-z0-9_-]*$/;
  /** @type {Readonly<Record<string, string>>} */
  const HIGHLIGHT_ENTITIES = Object.freeze({
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#x27;": "'",
  });
  /** @type {TextEncoder | null} */
  let syntaxTextEncoder = null;
  // Whether the prefetched optional assets have all settled. The event says so once;
  // this module loads with the first view, which can be after it, so the shell's
  // prefetch chain also leaves METABROWSER_OPTIONAL_ASSETS_SETTLED behind it.
  let syntaxAssetsSettled = global.METABROWSER_OPTIONAL_ASSETS_SETTLED === true;
  if (typeof global.addEventListener === "function") {
    global.addEventListener("metabrowser:optional-assets-loaded", () => {
      syntaxAssetsSettled = true;
    });
  }

  function syntaxHighlightMaxBytes() {
    const configured = Number(
      /** @type {{SYNTAX_HIGHLIGHT_MAX_BYTES?: unknown} | undefined} */ (
        global.METABROWSER_SETTINGS
      )?.SYNTAX_HIGHLIGHT_MAX_BYTES,
    );
    return Number.isFinite(configured) && configured >= 0 ? configured : 0;
  }

  /** @param {string} value */
  function utf8ByteLength(value) {
    syntaxTextEncoder ??= new global.TextEncoder();
    return syntaxTextEncoder.encode(value).byteLength;
  }

  /**
   * Record one safe plain-text fallback without making diagnostics part of
   * the syntax service's correctness path. Labels are fixed-cardinality and
   * metadata never includes source text.
   * @param {"over_limit" | "no_grammar" | "markup_rejected" | "lexer_threw"} reason
   * @param {string} language
   * @param {number} inputBytes
   */
  function recordSyntaxFallback(reason, language, inputBytes) {
    const recorder = global.metabrowser?.perf;
    if (typeof recorder?.measure !== "function") {
      return;
    }
    try {
      recorder.measure(`syntaxHighlight:fallback:${reason}`, () => undefined, {
        input_bytes: inputBytes,
        language: String(language).slice(0, 80),
      });
    } catch (_diagnosticError) {
      // Plain-text fallback must remain safe when an injected profiler fails.
    }
  }

  /** @param {string} language */
  function syntaxGrammarReady(language) {
    return (
      typeof global.hljs?.highlight === "function" &&
      typeof global.hljs?.getLanguage === "function" &&
      Boolean(global.hljs.getLanguage(language))
    );
  }

  function syntaxAbortError() {
    return new global.DOMException("Syntax highlighting was aborted.", "AbortError");
  }

  /**
   * Wait for a requested grammar or the terminal optional-asset event.
   * @param {string} language
   * @param {AbortSignal | undefined} signal
   * @returns {Promise<boolean>}
   */
  function waitForSyntaxAssets(language, signal) {
    if (signal?.aborted) {
      return Promise.reject(syntaxAbortError());
    }
    if (syntaxGrammarReady(language)) {
      return Promise.resolve(true);
    }
    if (syntaxAssetsSettled || typeof global.addEventListener !== "function") {
      return Promise.resolve(false);
    }
    return new Promise((resolve, reject) => {
      function cleanup() {
        global.removeEventListener("metabrowser:optional-asset-loaded", onAsset);
        global.removeEventListener("metabrowser:optional-assets-loaded", onTerminal);
        signal?.removeEventListener("abort", onAbort);
      }
      function onAsset() {
        if (syntaxGrammarReady(language)) {
          cleanup();
          resolve(true);
        }
      }
      function onTerminal() {
        cleanup();
        resolve(syntaxGrammarReady(language));
      }
      function onAbort() {
        cleanup();
        reject(syntaxAbortError());
      }
      global.addEventListener("metabrowser:optional-asset-loaded", onAsset);
      global.addEventListener("metabrowser:optional-assets-loaded", onTerminal);
      signal?.addEventListener("abort", onAbort, { once: true });
    });
  }

  /** @param {Record<string, any> | null | undefined} data */
  function isLargeTextPreview(data) {
    if (!data) {
      return false;
    }
    if (data.highlight_disabled) {
      return true;
    }
    if (typeof data.content === "string") {
      return utf8ByteLength(data.content) > syntaxHighlightMaxBytes();
    }
    const size = Number(data.size);
    return Number.isFinite(size) && size >= 0 && size > syntaxHighlightMaxBytes();
  }

  /**
   * Convert Highlight.js's constrained markup to token data without an HTML parser.
   * @param {string} markup
   * @returns {MetabrowserSyntaxTokenLines | null}
   */
  function scanHighlightMarkup(markup) {
    /** @type {MetabrowserSyntaxTokenLines} */
    const lines = [[]];
    /** @type {string[][]} */
    const classStack = [];
    let offset = 0;

    /** @param {string} text */
    function appendText(text) {
      if (text.length === 0) {
        return;
      }
      const classes = classStack.flat();
      const line = lines[lines.length - 1];
      const previous = line[line.length - 1];
      if (
        previous &&
        previous.classes.length === classes.length &&
        previous.classes.every((name, index) => name === classes[index])
      ) {
        previous.text += text;
      } else {
        line.push({ classes, text });
      }
    }

    while (offset < markup.length) {
      if (markup.startsWith("</span>", offset)) {
        if (classStack.length === 0) {
          return null;
        }
        classStack.pop();
        offset += "</span>".length;
        continue;
      }
      if (markup.startsWith('<span class="', offset)) {
        const end = markup.indexOf('">', offset);
        if (end < 0) {
          return null;
        }
        const opening = markup.slice(offset, end + 2);
        const match = /^<span class="([^"]+)">$/.exec(opening);
        const classes = match?.[1].split(" ") ?? [];
        if (
          classes.length === 0 ||
          !classes.some((name) => name.startsWith("hljs-")) ||
          !classes.every((name) => HIGHLIGHT_TOKEN_CLASS_RE.test(name))
        ) {
          return null;
        }
        classStack.push(classes);
        offset = end + 2;
        continue;
      }
      const character = markup[offset];
      if (character === "<") {
        return null;
      }
      if (character === "&") {
        const end = markup.indexOf(";", offset);
        if (end < 0) {
          return null;
        }
        const entity = markup.slice(offset, end + 1);
        const decoded = HIGHLIGHT_ENTITIES[entity];
        if (decoded === undefined) {
          return null;
        }
        appendText(decoded);
        offset = end + 1;
        continue;
      }
      if (character === "\n") {
        lines.push([]);
        offset += 1;
        continue;
      }
      let end = offset + 1;
      while (end < markup.length && !"<&\n".includes(markup[end])) {
        end += 1;
      }
      appendText(markup.slice(offset, end));
      offset = end;
    }
    return classStack.length === 0 ? lines : null;
  }

  /**
   * Highlight source through the host grammar registry and return DOM-free token lines.
   * @param {string} source
   * @param {string} language
   * @param {{signal?: AbortSignal}} [options]
   * @returns {Promise<MetabrowserSyntaxTokenLines | null>}
   */
  async function highlightSyntax(source, language, options = {}) {
    if (options.signal?.aborted) {
      throw syntaxAbortError();
    }
    const inputBytes = utf8ByteLength(source);
    if (inputBytes > syntaxHighlightMaxBytes()) {
      recordSyntaxFallback("over_limit", language, inputBytes);
      return null;
    }
    if (!(await waitForSyntaxAssets(language, options.signal))) {
      recordSyntaxFallback("no_grammar", language, inputBytes);
      return null;
    }
    if (options.signal?.aborted) {
      throw syntaxAbortError();
    }
    try {
      const result = global.hljs.highlight(source, { language, ignoreIllegals: true });
      if (!result || typeof result.value !== "string") {
        recordSyntaxFallback("markup_rejected", language, inputBytes);
        return null;
      }
      const lines = scanHighlightMarkup(result.value);
      const sourceLines = source.split("\n");
      if (
        lines === null ||
        lines.length !== sourceLines.length ||
        lines.some((runs, index) => runs.map((run) => run.text).join("") !== sourceLines[index])
      ) {
        recordSyntaxFallback("markup_rejected", language, inputBytes);
        return null;
      }
      return lines;
    } catch (_error) {
      recordSyntaxFallback("lexer_threw", language, inputBytes);
      return null;
    }
  }

  /**
   * How much of a partially-loaded payload is showing, or null when it is
   * complete. One reading of the payload, so the banner, the footer control,
   * and the header readout cannot disagree about whether more remains.
   *
   * @param {Record<string, any> | null | undefined} data
   * @returns {{loaded: string, total: string} | null}
   */
  function textPreviewProgress(data) {
    if (!data) {
      return null;
    }
    const totalBytes = data.size_uncompressed || data.logical_size || data.size || 0;
    const bytesRead = data.bytes_read || data.content_bytes || 0;
    const truncated =
      !!data.content_truncated ||
      (typeof data.bytes_read === "number" && totalBytes > 0 && bytesRead < totalBytes);
    if (!truncated) {
      return null;
    }
    return { loaded: formatSize(bytesRead), total: formatSize(totalBytes) };
  }

  /**
   * The Load more control itself. Emitted at both ends of partial content —
   * see docs/design-system.md, "Continuing partial content": a reader who has
   * scrolled to the end of what loaded is exactly the reader who wants more,
   * and sending them back to the top to ask for it is the whole problem.
   *
   * @param {"top" | "bottom"} position
   * @param {string | null | undefined} action
   * @returns {string}
   */
  function loadMoreButtonHtml(position, action) {
    // `action: null` means the caller wires its own listener — a view that
    // tracks its own offsets cannot be continued by the shell's text loader.
    // Otherwise the SDK's delegated listener runs the registered action it names
    // as "name()": the shell's text loader by default. No inline handler is
    // written, so the page policy for an untrusted source needs none.
    const named = typeof action === "string" && action ? action : "loadMoreCurrentText()";
    const handler = action === null ? "" : ` data-mb-load-more="${escapeHtml(named)}"`;
    return (
      `<button class="btn metabrowser-load-more" type="button" data-position="${position}"` +
      `${handler}${delegateOwnerAttribute()} data-tip-text="Load more of this file">` +
      "Load more</button>"
    );
  }

  /**
   * The shared partial-content notice.
   *
   * Every surface that says "this is only part of the file" is this box, in
   * core and in plugins alike — see docs/design-system.md, "Continuing partial
   * content". A use-site class rides along for querying and positioning, but
   * `partial-notice` is what carries the fill, border, and type, so the two
   * ends of a file and the two views cannot drift apart.
   *
   * `showControl: false` states the condition without offering to continue —
   * for content that is partial and will stay partial, such as a file larger
   * than a view is willing to load. That is still a partial-content notice; a
   * reader who cannot see the whole file needs telling either way.
   *
   * @param {{loaded: string, total: string}} progress
   * @param {"top" | "bottom"} position
   * @param {{useSiteClass?: string, action?: string | null, hidden?: boolean,
   *          label?: string, showControl?: boolean}} [options]
   * @returns {string}
   */
  function partialNoticeHtml(progress, position, options) {
    const useSiteClass = options?.useSiteClass ? ` ${options.useSiteClass}` : "";
    const hidden = options?.hidden ? " hidden" : "";
    const label = options?.label ?? "Partial file.";
    const control =
      options?.showControl === false ? "" : loadMoreButtonHtml(position, options?.action);
    return (
      `<div class="notice partial-notice${useSiteClass}" data-severity="warning"` +
      ` data-position="${position}" role="status"${hidden}>` +
      // The progress figures live in their own element so a view that updates
      // in place can rewrite them without taking the label with them.
      `<span><strong class="partial-notice-label">${escapeHtml(label)}</strong> ` +
      '<span class="partial-notice-readout">Showing ' +
      escapeHtml(progress.loaded) +
      " of " +
      escapeHtml(progress.total) +
      ".</span></span>" +
      // The notice carries its own button. It used to say "Select Load more to
      // continue" and point at a control in the pane header, which puts the
      // explanation and the remedy in different places.
      control +
      "</div>"
    );
  }

  /**
   * The partial-content banner, mounted before the content.
   *
   * @param {Record<string, any> | null | undefined} data
   * @returns {string}
   */
  function renderTextTruncationWarning(data) {
    const progress = textPreviewProgress(data);
    return progress
      ? partialNoticeHtml(progress, "top", {
          useSiteClass: "metabrowser-source-truncation-warning",
        })
      : "";
  }

  /**
   * Trailing companion to the banner, mounted after the content.
   *
   * @param {Record<string, any> | null | undefined} data
   * @returns {string}
   */
  function renderTextLoadMoreFooter(data) {
    const progress = textPreviewProgress(data);
    return progress
      ? partialNoticeHtml(progress, "bottom", { useSiteClass: "metabrowser-source-more-footer" })
      : "";
  }

  // Copy-icon SVG. Defined here (not pulled from window.MetabrowserIcons)
  // so plugins don't depend on the icons.js bundle being loaded first.
  const ICON_COPY =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round">' +
    '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>' +
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>' +
    "</svg>";

  /** @param {string} innerHtml */
  function wrapWithCopy(innerHtml) {
    // A delegated click listener (installed once at SDK init) handles
    // .content-copy-btn clicks and copies the wrapped <code> text; no
    // inline handler is needed.
    return (
      '<div class="content-copy-wrap">' +
      '<button class="icon-btn icon-btn-reveal icon-btn-overlay content-copy-btn"' +
      ' type="button" data-mb-copy="wrap"' +
      delegateOwnerAttribute() +
      ' data-tip-text="Copy content" aria-label="Copy content">' +
      ICON_COPY +
      "</button>" +
      innerHtml +
      "</div>"
    );
  }

  /**
   * The server's syntax-language tables, which the settings type does not name.
   *
   * @typedef {{
   *   SYNTAX_LANGUAGE_BY_BASENAME?: Record<string, string>,
   *   SYNTAX_LANGUAGE_BY_EXTENSION?: Record<string, string>,
   * }} SyntaxLanguageSettings
   */

  function syntaxLanguageSettings() {
    const settings = /** @type {SyntaxLanguageSettings} */ (global.METABROWSER_SETTINGS || {});
    return settings;
  }

  /** @param {string} ext */
  function langForExtension(ext) {
    const languageByExtension = syntaxLanguageSettings().SYNTAX_LANGUAGE_BY_EXTENSION || {};
    return languageByExtension[ext || ""] || "";
  }

  /** @param {string} pathOrName @param {string} [ext] */
  function langForPath(pathOrName, ext = "") {
    const languageByBasename = syntaxLanguageSettings().SYNTAX_LANGUAGE_BY_BASENAME || {};
    const pathParts = String(pathOrName || "")
      .replaceAll("\\", "/")
      .split("/");
    let basename = (pathParts[pathParts.length - 1] || "").toLowerCase();
    for (const compressionSuffix of [".gz", ".zlib"]) {
      if (basename.endsWith(compressionSuffix)) {
        basename = basename.slice(0, -compressionSuffix.length);
        break;
      }
    }
    let logicalExtension = ext.toLowerCase();
    if (!logicalExtension) {
      const dot = basename.lastIndexOf(".");
      logicalExtension = dot > 0 ? basename.slice(dot) : "";
    }
    return languageByBasename[basename] || langForExtension(logicalExtension);
  }

  /**
   * Render the shared bounded Source surface used by generic text-like views.
   *
   * `options.parts` shows the text in consecutive code blocks under one gutter, each
   * highlighted in its own language, such as a Markdown file's YAML front matter and
   * its body. The parts must join to the content, and every part but the last must end
   * with a newline. The text shows as one block instead when the parts do not, when the
   * file is too large to highlight, and when only part of it is loaded, because Load
   * more appends to the one block.
   *
   * @param {HTMLElement} container
   * @param {Record<string, unknown> & {content?: string, ext?: string}} data
   * @param {{parts?: ReadonlyArray<Readonly<{text: string, language: string}>>}} [options]
   */
  function renderSourceView(container, data, options = {}) {
    const truncationWarning = renderTextTruncationWarning(data);
    const loadMoreFooter = renderTextLoadMoreFooter(data);
    const content = typeof data.content === "string" ? data.content : "";
    const large = isLargeTextPreview(data);
    let languageClass = "plaintext no-highlight";
    if (!large) {
      const language = langForPath(
        typeof data.path === "string" ? data.path : "",
        typeof data.ext === "string" ? data.ext : "",
      );
      languageClass = language ? `language-${language}` : "plaintext";
    }
    // Line numbers and #L anchors are part of a Source view's first paint.
    // The HTML parser turns CR and CRLF into LF, so the gutter counts the same text.
    const normalize = (/** @type {string} */ text) => text.replace(/\r\n?/g, "\n");
    const text = normalize(content);
    // Each part starts on a line of its own, so every part but the last ends a line;
    // then the gutter's count of the whole text is the lines the parts show.
    const given = Array.isArray(options.parts) ? options.parts : [];
    const parts =
      !large &&
      !data.content_truncated &&
      given.length > 1 &&
      given.map((part) => normalize(part.text)).join("") === text &&
      given.slice(0, -1).every((part) => normalize(part.text).endsWith("\n"))
        ? given.map((part) => ({
            text: part.text,
            languageClass: /^[A-Za-z0-9_+-]+$/.test(part.language)
              ? `language-${part.language}`
              : "plaintext",
          }))
        : [{ text: content, languageClass }];
    const codes = parts
      .map(
        (part) => `<code class="${part.languageClass}">${escapeHtml(normalize(part.text))}</code>`,
      )
      .join("");
    // Copy takes the first code element in the wrap, so several parts copy one payload.
    const payload =
      parts.length > 1
        ? `<code data-mb-copy-payload class="no-highlight" hidden>${escapeHtml(text)}</code>`
        : "";
    const code =
      `${payload}<pre class="code-block metabrowser-source-lines">${lineAnchors.gutterHtml(text)}` +
      `${codes}</pre>`;
    container.classList.add("metabrowser-source-host");
    container.innerHTML = truncationWarning + wrapWithCopy(code) + loadMoreFooter;
    // The shell's navigation takes the `replace` option the gutter passes; its
    // declared option type is the plugin-facing one, which does not name it.
    const navigation = /** @type {Parameters<typeof lineAnchors.mount>[1]["navigation"]} */ (
      /** @type {unknown} */ (global.MetabrowserNavigationRoute?.navigation ?? null)
    );
    lineAnchors.mount(container, {
      path: typeof data.path === "string" ? data.path : "",
      truncated: !!data.content_truncated,
      navigation,
    });
  }

  Object.assign(mb, {
    highlightSyntax: highlightSyntax,
    isLargeTextPreview: isLargeTextPreview,
    langForExtension: langForExtension,
    langForPath: langForPath,
    partialNoticeHtml: partialNoticeHtml,
    renderSourceView: renderSourceView,
    renderTextLoadMoreFooter: renderTextLoadMoreFooter,
    renderTextTruncationWarning: renderTextTruncationWarning,
    wrapWithCopy: wrapWithCopy,
  });
})(/** @type {Window & typeof globalThis} */ (typeof window !== "undefined" ? window : globalThis));
