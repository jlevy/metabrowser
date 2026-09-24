// Line numbers and GitHub-style line anchors in source views.
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
    return (
      '<span class="source-line-numbers" role="slider" tabindex="0" aria-label="Line numbers" ' +
      `aria-orientation="vertical" aria-valuemin="1">${gutterText(countLines(text))}</span>`
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
    view.status.textContent = lit && !focused ? `${spoken(view.state)} highlighted.` : "";
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
   * @param {View} view
   * @param {KeyboardEvent} event
   */
  function handleGutterKey(view, event) {
    if (event.altKey || event.ctrlKey || event.metaKey) {
      return;
    }
    const pitch = linePitch(view);
    const top = view.gutter.getBoundingClientRect().top;
    const height = global.innerHeight;
    const step = keyStep(view.applied, view.focus, event.key, event.shiftKey, {
      lines: view.loaded.lines,
      page: pitch > 0 && height > 0 ? Math.floor(height / pitch) - 1 : 1,
      origin: pitch > 0 && top < 0 ? lineAt(-top, pitch, view.loaded.lines) : 1,
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
