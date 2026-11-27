// View-phase code: what a view's renderer calls, and the first tree does not.
//
// plugin-sdk.js is a startup script, so every byte of it is fetched before the first
// tree paints. Two things are here instead, in one file because nothing uses either
// without the other: a Source view's line gutter and `#L` anchors
// (`window.MetabrowserSourceLineAnchors`), and the SDK helpers that build a view's
// markup -- the Source surface, ref chips and their action menus, the copy
// wrapper, age labels and the partial-content notice -- with
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

  /**
   * A source view's text with every line ending as LF: CRLF and a lone CR each become
   * one LF. It is what countLines counts and what a copy takes. A view's first render
   * and each part Load more appends go through this one function, so the text reads
   * the same however it was loaded.
   *
   * A file is loaded in parts cut at byte offsets, which can fall between a CR and its
   * LF. `afterCarriageReturn` says the text loaded before this one ended with a CR,
   * which was shown as a line ending already; an LF that starts this text is the rest
   * of that ending and adds no line. So the parts of a text, each normalized with the
   * flag for the part before it, join to the whole text normalized.
   *
   * @param {string} text
   * @param {boolean} [afterCarriageReturn]
   */
  function normalizeLineEndings(text, afterCarriageReturn = false) {
    const rest = afterCarriageReturn && text.startsWith("\n") ? text.slice(1) : text;
    return rest.includes("\r") ? rest.replace(/\r\n?/g, "\n") : rest;
  }

  /**
   * The gutter's numbers for lines `from + 1` through `lines`, each on its own line.
   * After line `from`, the text starts with the newline that ends that line.
   *
   * @param {number} lines
   * @param {number} [from]
   */
  function gutterText(lines, from = 0) {
    const numbers = new Array(Math.max(0, lines - from));
    for (let index = 0; index < numbers.length; index++) {
      numbers[index] = from + index + 1;
    }
    return (from > 0 && numbers.length > 0 ? "\n" : "") + numbers.join("\n");
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
   * Number the lines Load more appended to a view. An append only adds lines (a view
   * rendered again is a new view), so the numbers after the ones the gutter shows are
   * appended as the text is, in text nodes of at most 64 KiB (source-append.js, which
   * Load more loads before it refreshes). Writing every number into the gutter's first
   * text node instead cost a node of millions of characters per click, which WebKit
   * lays out slowly, and in WebKit left the rest of the nodes its HTML parser had split
   * the gutter into on screen after the new numbers.
   *
   * @param {View} view
   * @param {number} lines
   */
  function appendNumbers(view, lines) {
    const { gutter } = view;
    const owner = gutter.ownerDocument;
    const fragment = owner.createDocumentFragment();
    const added = gutterText(lines, view.loaded.lines);
    for (const piece of global.MetabrowserSourceAppend.textPieces(added)) {
      fragment.appendChild(owner.createTextNode(piece));
    }
    // Before the scroll target, which follows the numbers it is placed over.
    gutter.insertBefore(fragment, view.target?.parentNode === gutter ? view.target : null);
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
      if (lines > view.loaded.lines) {
        appendNumbers(view, lines);
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
    normalizeLineEndings,
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
  const { delegateOwnerAttribute, ownDelegate, escapeHtml, formatSize } = mb;

  /**
   * @typedef {{
   *   label?: string, kind?: string, trunk?: boolean, head?: boolean,
   *   menu?: "inline" | "sibling" | false, copy?: "inline" | "sibling" | false,
   *   ref?: string, repository?: string | null, snapshot?: string, current?: boolean,
   * }} RefChipOptions
   */

  /** @param {string} name @param {RefChipOptions} options */
  function refChipParts(name, options) {
    const kind = options.kind === "tag" ? "tag" : options.kind === "remote" ? "remote" : "local";
    const menu = options.menu ?? options.copy ?? "inline";
    const label = options.label ?? name;
    const classes = ["git-ref", `git-ref-${kind}`];
    if (options.trunk) {
      classes.push("git-ref-trunk");
    }
    if (options.head) {
      classes.push("git-ref-head");
    }
    if (menu === "inline") {
      classes.push("git-ref-action", "disclosure-toggle");
    }
    return {
      tag: menu === "inline" ? "button" : "span",
      className: classes.join(" "),
      label,
      action: menu
        ? JSON.stringify({
            name,
            label,
            kind,
            ref: options.ref,
            repository: options.repository,
            snapshot: options.snapshot,
            current: options.current,
          })
        : null,
    };
  }

  const refCaret = () =>
    `<span class="git-ref-menu-caret" aria-hidden="true">${global.MetabrowserIcons?.toggle ?? ""}</span>`;

  /** @param {string} name @param {RefChipOptions} [options] */
  function refChipHtml(name, options = {}) {
    const { tag, className, label, action } = refChipParts(name, options);
    const button = tag === "button";
    return (
      `<${tag} class="${className}" data-tip-text="${escapeHtml(label)}"` +
      (action ? ` data-ref-menu="${escapeHtml(action)}"` : "") +
      (button
        ? ` type="button" aria-haspopup="menu" aria-expanded="false" aria-label="Actions for ${escapeHtml(label)}"${delegateOwnerAttribute()}`
        : "") +
      `><span class="git-ref-label">${escapeHtml(label)}</span>` +
      (button ? refCaret() : "") +
      `</${tag}>`
    );
  }

  /** @param {HTMLButtonElement} button @param {string} label */
  function configureRefTrigger(button, label) {
    button.type = "button";
    button.setAttribute("aria-haspopup", "menu");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-label", `Actions for ${label}`);
    ownDelegate(button);
  }

  /** @param {string} name @param {RefChipOptions} [options] @returns {HTMLElement} */
  function refChip(name, options = {}) {
    const { tag, className, label, action } = refChipParts(name, options);
    const chip = document.createElement(tag);
    chip.className = className;
    chip.dataset.tipText = label;
    const text = document.createElement("span");
    text.className = "git-ref-label";
    text.textContent = label;
    chip.append(text);
    if (action) {
      chip.setAttribute("data-ref-menu", action);
    }
    if (tag === "button") {
      configureRefTrigger(/** @type {HTMLButtonElement} */ (chip), label);
      const caret = document.createElement("span");
      caret.className = "git-ref-menu-caret";
      caret.setAttribute("aria-hidden", "true");
      caret.innerHTML = global.MetabrowserIcons?.toggle || "";
      chip.append(caret);
    }
    return chip;
  }

  /** What the arrow between a merge's two branches is called: a reader hears "wip merges
   * into topic". */
  const MERGE_ARROW_NAME = "merges into";

  /**
   * A merge, in the one notation every surface uses: the source branch, an arrow, then the
   * target branch, left to right (docs/design-system.md, "Merge Direction"). For a pull
   * request the source is its head and the target its base. Each side is a `refChip`, and
   * `options` applies to both.
   *
   * The group is a left-to-right island (`dir="ltr"`), as a path is, so the arrow points
   * from the source to the target in a right-to-left page too, and its order in the
   * document, source first, is the order a screen reader reads.
   *
   * @param {{name: string} & RefChipOptions} source The branch whose commits merge.
   * @param {{name: string} & RefChipOptions} target The branch they merge into.
   * @param {RefChipOptions} [options]
   * @returns {HTMLElement}
   */
  function mergeRefs(source, target, options = {}) {
    /** @param {{name: string} & RefChipOptions} side @param {string} role */
    const chip = (side, role) => {
      const element = refChip(side.name, { ...options, ...side });
      element.classList.add(role);
      return element;
    };
    const arrow = document.createElement("span");
    arrow.className = "merge-refs-arrow";
    arrow.setAttribute("role", "img");
    arrow.setAttribute("aria-label", MERGE_ARROW_NAME);
    // No tooltip: it would restate the two names beside it, and a chip cut short carries
    // its own (docs/design-system.md, "Tooltips Add Information").
    // The spaces are text, so a copied selection reads "wip → topic".
    arrow.textContent = " → ";
    const group = document.createElement("span");
    group.className = "merge-refs";
    group.setAttribute("dir", "ltr");
    group.append(chip(source, "merge-refs-source"), arrow, chip(target, "merge-refs-target"));
    return group;
  }

  /** @type {WeakMap<HTMLButtonElement, Element>} */
  const refMenuSourceChips = new WeakMap();

  /** Overlay full-chip menu buttons as siblings of clickable rows and picker buttons.
   * Read geometry on entry and remove its listeners when the controls are hidden or recycled.
   * @param {HTMLElement} primary
   * @param {HTMLElement} host
   * @returns {() => void}
   */
  function mountRefMenus(primary, host) {
    const chips = [...primary.querySelectorAll("[data-ref-menu]")];
    if (!chips.length) {
      return () => {};
    }
    host.classList.add("git-ref-menu-host");
    const layer = document.createElement("span");
    layer.className = "git-ref-menu-layer";
    const buttons = chips.map((chip) => {
      const button = document.createElement("button");
      button.className = "git-ref-menu-hit disclosure-toggle";
      const label = chip.getAttribute("data-tip-text") ?? "";
      configureRefTrigger(button, label);
      button.setAttribute("data-ref-menu", chip.getAttribute("data-ref-menu") ?? "");
      refMenuSourceChips.set(button, chip);
      button.innerHTML = refCaret();
      layer.append(button);
      return button;
    });
    host.append(layer);
    let hiding = false;
    function hide() {
      hiding = true;
      const active = document.activeElement;
      const menu = activeRefMenu;
      const owned = menu !== null && layer.contains(menu.trigger);
      const restore = layer.contains(active) || (owned && menu.menu.contains(active));
      if (owned) {
        menu.close(false);
      }
      if (restore) {
        primary.focus({ preventScroll: true });
      }
      global.removeEventListener("resize", hide);
      document.removeEventListener("scroll", hideOnScroll, true);
      document.removeEventListener("pointerdown", outsidePointer, true);
      layer.hidden = true;
      for (const button of buttons) {
        button.tabIndex = -1;
      }
      hiding = false;
    }
    /** @param {Event} event */
    function hideOnScroll(event) {
      if (!insideRefMenu(event?.target ?? null)) {
        hide();
      }
    }
    /** A pane splitter may prevent focus movement while changing the clipping box.
     * Release the overlay before that drag. The open menu handles its own dismissal.
     * @param {PointerEvent} event
     */
    function outsidePointer(event) {
      if (
        !host.contains(/** @type {Node | null} */ (event.target)) &&
        !insideRefMenu(event.target)
      ) {
        hide();
      }
    }
    function position() {
      if (hiding) {
        return;
      }
      const box = host.getBoundingClientRect();
      const primaryBox = primary.getBoundingClientRect();
      layer.hidden = false;
      for (let index = 0; index < chips.length; index++) {
        const rect = chips[index].getBoundingClientRect();
        // A chip can fit its own group yet be clipped by a narrower metadata line.
        // Keep the sibling hit target inside every containing box through the primary.
        let left = primaryBox.left;
        let right = primaryBox.right;
        for (
          let ancestor = chips[index].parentElement;
          ancestor;
          ancestor = ancestor.parentElement
        ) {
          const box = ancestor.getBoundingClientRect();
          left = Math.max(left, box.left);
          right = Math.min(right, box.right);
          if (ancestor === primary) {
            break;
          }
        }
        const button = buttons[index];
        const visibleLeft = Math.max(rect.left, left);
        const visibleRight = Math.min(rect.right, right);
        button.hidden = visibleRight <= visibleLeft;
        button.style.left = `${visibleLeft - box.left}px`;
        button.style.top = `${rect.top - box.top}px`;
        button.style.width = `${Math.max(0, visibleRight - visibleLeft)}px`;
        button.style.height = `${rect.height}px`;
        button.tabIndex = button.hidden ? -1 : 0;
      }
      global.addEventListener("resize", hide);
      document.addEventListener("scroll", hideOnScroll, true);
      document.addEventListener("pointerdown", outsidePointer, true);
    }
    /** @param {FocusEvent | PointerEvent} event */
    function leave(event) {
      if (
        !host.contains(/** @type {Node | null} */ (event.relatedTarget)) &&
        !insideRefMenu(event.relatedTarget) &&
        !(activeRefMenu && layer.contains(activeRefMenu.trigger)) &&
        (event.type === "focusout" || !host.contains(document.activeElement))
      ) {
        hide();
      }
    }
    /** @param {MouseEvent} event */
    function openChip(event) {
      const at = chips.findIndex((chip) =>
        chip.contains(/** @type {Node | null} */ (event.target)),
      );
      if (at < 0) {
        return;
      }
      event.stopPropagation();
      event.preventDefault();
      position();
      buttons[at].click();
    }
    hide();
    primary.addEventListener("click", openChip, true);
    host.addEventListener("pointerenter", position);
    host.addEventListener("focusin", position);
    host.addEventListener("pointerleave", leave);
    host.addEventListener("focusout", leave);
    return () => {
      hide();
      primary.removeEventListener("click", openChip, true);
      host.removeEventListener("pointerenter", position);
      host.removeEventListener("focusin", position);
      host.removeEventListener("pointerleave", leave);
      host.removeEventListener("focusout", leave);
      layer.remove();
    };
  }

  /** @typedef {{name: string, label: string, kind: string, ref?: string,
   * repository?: string | null, snapshot?: string, current?: boolean}} RefMenuData */
  /** @type {{ trigger: HTMLButtonElement, menu: HTMLElement, close(focus: boolean): void } | null} */
  let activeRefMenu = null;
  let refMenuIsSwitching = false;
  let refMenuContextId = 0;

  /** @param {EventTarget | null} target */
  function insideRefMenu(target) {
    return activeRefMenu !== null && target instanceof Node && activeRefMenu.menu.contains(target);
  }

  /** @param {RefMenuData} data */
  function refDestination(data) {
    const context =
      global.METABROWSER_CHECKOUT_REF_CONTEXT ??
      global.METABROWSER_REPOSITORY_CONTEXT ??
      mb.repository;
    const tag = data.kind === "tag";
    const isMirror =
      !global.METABROWSER_SOURCE_CHECKOUT &&
      Boolean(
        global.METABROWSER_SOURCE_PIN &&
          global.document.querySelector(".header-path[data-mirror-location]"),
      );
    // A checkout's origin is the only remote in the shell context. Local tags carry
    // no remote provenance. A GitHub pull's sides supply their own repository.
    const origin = context?.host === "github.com" ? `${context.owner}/${context.name}` : null;
    const originBranch = data.ref?.startsWith("refs/remotes/origin/");
    const checkedOriginBranch =
      data.ref === `refs/heads/${context?.branch}` && context?.branch_on_origin;
    const hosted =
      data.repository !== undefined
        ? data.repository
        : originBranch || checkedOriginBranch || (isMirror && tag)
          ? origin
          : null;
    const name =
      data.repository === undefined
        ? (/^refs\/remotes\/[^/]+\/(.+)$/.exec(data.ref ?? "")?.[1] ?? data.name)
        : data.name;
    const parts = name.split("/");
    const url =
      hosted &&
      /^[a-z0-9-]+\/[a-z0-9_.-]+$/i.test(hosted) &&
      hosted.split("/").every((part) => part !== "." && part !== "..") &&
      parts.every((part) => part !== "" && part !== "." && part !== ".." && !part.includes("\\"))
        ? "https://github.com/" +
          hosted +
          "/tree/refs/" +
          (tag ? "tags/" : "heads/") +
          parts.map(encodeURIComponent).join("/")
        : null;
    return { name, url, origin, isMirror };
  }

  /** @param {RefMenuData} data @param {HTMLElement} status */
  async function visitRef(data, status) {
    if (!data.ref || refMenuIsSwitching) {
      return;
    }
    refMenuIsSwitching = true;
    status.textContent = "Opening…";
    /** @type {(leaving: boolean) => void} */
    let decided = () => {};
    let leaving = false;
    const held = global.MetabrowserSourcePinGuard?.hold(
      new Promise((resolve) => {
        decided = resolve;
      }),
    );
    if (held === false) {
      decided(false);
      refMenuIsSwitching = false;
      status.textContent = "Another switch is already in progress.";
      return;
    }
    try {
      const selection = data.snapshot ? { oid: data.snapshot, under: data.ref } : { ref: data.ref };
      const response = await global.fetch("/api/source/pin", {
        method: "POST",
        headers: { "content-type": "application/json" },
        cache: "no-store",
        body: JSON.stringify(selection),
      });
      if (response.status === 200) {
        global.location.assign("/view/");
        leaving = true;
      } else {
        // The answer's words and code are an agent's (`metab --api`); the menu says what
        // the reader can do (docs/design-system-messages.md).
        status.textContent =
          response.status === 202
            ? "This branch or tag is still being fetched. Try again shortly."
            : "Could not open this branch or tag.";
      }
    } catch {
      status.textContent = "Could not open this branch or tag.";
    } finally {
      decided(leaving);
      if (!leaving) {
        refMenuIsSwitching = false;
      }
    }
  }

  /** @param {HTMLButtonElement} trigger @param {boolean} last */
  function openRefMenu(trigger, last = false) {
    if (activeRefMenu?.trigger === trigger) {
      activeRefMenu.close(true);
      return;
    }
    activeRefMenu?.close(false);
    const raw = trigger.getAttribute("data-ref-menu");
    if (!raw) {
      return;
    }
    const data = /** @type {RefMenuData} */ (JSON.parse(raw));
    const tag = data.kind === "tag";
    const kind = tag ? "Tag" : data.kind === "remote" ? "Remote branch" : "Local branch";
    const { name, url, origin, isMirror } = refDestination(data);
    const viewable = data.snapshot
      ? isMirror
      : (isMirror || global.METABROWSER_SOURCE_CHECKOUT) &&
        (data.repository === undefined ||
          (origin !== null && data.repository?.toLowerCase() === origin.toLowerCase()));
    const doc = global.document;
    const menu = doc.createElement("div");
    menu.className = "menu git-ref-menu";
    menu.setAttribute("data-ref-action-menu", "");
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", `${kind} ${data.label}`);
    const context = doc.createElement("div");
    context.className = "menu-link-url";
    const contextId = `git-ref-menu-${++refMenuContextId}`;
    context.setAttribute("id", contextId);
    context.setAttribute("aria-hidden", "true");
    context.textContent = `${kind} · ${data.label}`;
    const status = doc.createElement("div");
    status.className = "git-ref-menu-status";
    status.setAttribute("role", "status");
    const copy = doc.createElement("button");
    copy.type = "button";
    renderLinkMenuItem(
      copy,
      tag ? "Copy Tag Name" : "Copy Branch Name",
      global.MetabrowserIcons?.copy ?? "",
    );
    copy.addEventListener("click", async () => {
      try {
        if (!global.navigator.clipboard) {
          throw new Error("Clipboard unavailable");
        }
        await global.navigator.clipboard.writeText(name);
        status.textContent = tag ? "Tag name copied" : "Branch name copied";
      } catch {
        status.textContent = "Copy failed";
      }
    });
    /** @type {HTMLElement[]} */
    const items = [copy];
    if (data.ref && viewable && !data.current) {
      const view = doc.createElement("button");
      view.type = "button";
      renderLinkMenuItem(
        view,
        data.snapshot ? "View PR Head in Metabrowser" : tag ? "View This Tag" : "View This Branch",
        destinationGlyphs.arrowRight,
      );
      view.addEventListener("click", () => void visitRef(data, status));
      items.push(view);
    }
    const destination = doc.createElement("div");
    if (url) {
      destination.className = "menu-link-url";
      destination.textContent = url;
      destination.setAttribute("id", `${contextId}-url`);
      destination.setAttribute("aria-hidden", "true");
      const open = externalLinkMenuItem(url, "Open on GitHub", () => close(true));
      open.setAttribute("aria-describedby", `${contextId}-url`);
      items.push(open);
    }
    for (const item of items) {
      if (!item.hasAttribute("aria-describedby")) {
        item.setAttribute("aria-describedby", contextId);
      }
    }
    menu.append(context, ...items, status);
    if (url) {
      menu.insertBefore(destination, items.at(-1) ?? status);
    }
    // A nested menu stays inside its native disclosure's focus boundary but outside
    // the scrolling panel, so it can still be positioned and read at the viewport.
    const disclosure = /** @type {HTMLDetailsElement | null} */ (
      trigger.closest("details[data-ref-menu-container]")
    );
    (disclosure ?? doc.body).append(menu);

    const controller = new AbortController();
    const signal = controller.signal;
    const observer = new MutationObserver(() => {
      if (!trigger.isConnected) {
        close(false);
      }
    });
    observer.observe(doc.body, { childList: true, subtree: true });

    const sourceChip = refMenuSourceChips.get(trigger);
    // It closes as every menu does (docs/design-system.md, "Every Menu Closes Alike"); a
    // press on the source chip beneath its overlay is the trigger's.
    const dismissal = global.metabrowser.menus?.dismissible({
      name: "git-ref-menu",
      trigger,
      inside: (node) => menu.contains(node) || Boolean(sourceChip?.contains(node)),
      isOpen: () => menu.isConnected,
      close: () => close(false),
    });
    /** @param {boolean} focus */
    function close(focus) {
      controller.abort();
      observer.disconnect();
      dismissal?.dispose();
      activeRefMenu = null;
      menu.remove();
      trigger.setAttribute("aria-expanded", "false");
      if (focus && trigger.isConnected) {
        trigger.focus({ preventScroll: true });
      }
    }
    activeRefMenu = { trigger, menu, close };
    disclosure?.addEventListener(
      "toggle",
      () => {
        if (!disclosure.open) {
          close(false);
        }
      },
      { signal },
    );
    trigger.setAttribute("aria-expanded", "true");
    const rect = trigger.getBoundingClientRect();
    const viewport = doc.documentElement;
    const margin = 6;
    menu.style.left =
      Math.max(margin, Math.min(rect.left, viewport.clientWidth - menu.offsetWidth - margin)) +
      "px";
    menu.style.top = `${Math.max(
      margin,
      rect.bottom + margin + menu.offsetHeight <= viewport.clientHeight
        ? rect.bottom + margin
        : rect.top - menu.offsetHeight - margin,
    )}px`;
    dismissal?.opened();
    items[last ? items.length - 1 : 0].focus({ preventScroll: true });
    // A press can land on the source chip beneath its overlay. Keep focus from moving to
    // the underlying row before it forwards the click.
    doc.addEventListener(
      "pointerdown",
      (event) => {
        if (event.target instanceof Node && sourceChip?.contains(event.target)) {
          event.preventDefault();
        }
      },
      { capture: true, signal },
    );
    doc.addEventListener(
      "scroll",
      (event) => {
        if (!insideRefMenu(event.target)) {
          close(true);
        }
      },
      { capture: true, signal },
    );
    global.addEventListener("resize", () => close(true), { signal });
    menu.addEventListener("keydown", (event) => {
      if (event.key === "Tab") {
        close(true);
        return;
      }
      if (event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const index = items.indexOf(/** @type {HTMLElement} */ (doc.activeElement));
      const next =
        event.key === "ArrowDown"
          ? (index + 1) % items.length
          : event.key === "ArrowUp"
            ? (index + items.length - 1) % items.length
            : event.key === "Home"
              ? 0
              : event.key === "End"
                ? items.length - 1
                : null;
      // Escape is the shared closing's, which gives focus back to the trigger.
      if (next === null) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      items[next].focus({ preventScroll: true });
    });
  }

  /** @param {Event} event */
  function refTrigger(event) {
    const target = /** @type {Element | null} */ (event.target);
    const button = target?.closest?.("button[data-ref-menu]");
    return button && global.MetabrowserPluginHost.isOwnedDelegate(button)
      ? /** @type {HTMLButtonElement} */ (button)
      : null;
  }
  global.document?.addEventListener?.("click", (event) => {
    const trigger = refTrigger(event);
    if (trigger) {
      openRefMenu(trigger);
    }
  });
  global.document?.addEventListener?.("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey) {
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
      return;
    }
    const trigger = refTrigger(event);
    if (!trigger) {
      return;
    }
    event.preventDefault();
    openRefMenu(trigger, event.key === "ArrowUp");
  });
  global.addEventListener?.("pageshow", (event) => {
    if (event.persisted) {
      refMenuIsSwitching = false;
    }
  });

  /**
   * The neutral person in an avatar's box where there is no avatar: Lucide 1.17.0's
   * `circle-user-round.svg`, at upstream commit 896aba0d195a4fec38ad7c4a90d00cb3389ebfea, as
   * the icon registry's glyphs are Lucide's (icons.js), drawn in the box's muted ink. Its ISC
   * copyright and license are the Lucide notice beside `destinationGlyphs` below, and
   * NOTICE.md lists it. It is here, beside the one component that draws it, in this view
   * bundle, and not in the registry, a startup script every folder's first paint fetches,
   * where it cost 92 compressed bytes (devtools/check_startup_scripts.py, 2026-11-16).
   */
  const PERSON_GLYPH = // Lucide `circle-user-round`
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M17.925 20.056a6 6 0 0 0-11.851.001"/><circle cx="12" cy="11" r="4"/>' +
    '<circle cx="12" cy="12" r="10"/></svg>';

  function personGlyph() {
    return PERSON_GLYPH;
  }

  /**
   * A person, as every page draws one (docs/design-system.md, "Actor Identity"): an
   * avatar's box, then the bold name in the shell's person-name primitive, `.actor-name`.
   * The box is `--actor-avatar-size` square from first paint whatever it holds, so the name
   * starts in one place with an avatar or without one, and an avatar that arrives later or
   * fails moves nothing. It holds the avatar where the caller has one, and the shell's
   * neutral person glyph where it has none; an avatar that fails to load gives its box to
   * the glyph.
   *
   * `avatar` is an https address the caller vouches for, as the GitHub plugin vouches for
   * GitHub's avatars (`avatarUrl` in its pull-page.js); anything else draws the glyph. The
   * image says nothing the name beside it does not, so its text is empty, and it sends no
   * referrer and no credentials, its size and privacy attributes set before its `src`.
   * Requested in anonymous CORS mode, it loads only from a host that sends
   * `Access-Control-Allow-Origin`, and in a folder served untrusted only from GitHub's
   * avatar host, which the page's policy admits (capabilities.py, `untrusted_shell_csp`);
   * any other image shows the glyph.
   * When it loads is its placement's, lazy unless the caller asks for eager
   * (docs/design-system.md, "A Repaint Keeps Its Images"). `placeholder: false` draws no box
   * for a person with no avatar, for a dense list row whose avatar comes with its row.
   *
   * @param {string} name
   * @param {{avatar?: string | null, loading?: "lazy" | "eager", className?: string,
   *   nameClass?: string, placeholder?: boolean}} [options]
   * @returns {HTMLElement}
   */
  function actorIdentity(name, options = {}) {
    const identity = document.createElement("span");
    identity.className = `actor-identity${options.className ? ` ${options.className}` : ""}`;
    const avatar =
      typeof options.avatar === "string" && options.avatar.startsWith("https://")
        ? options.avatar
        : null;
    if (avatar !== null || options.placeholder !== false) {
      const box = document.createElement("span");
      box.className = "actor-avatar";
      box.setAttribute("aria-hidden", "true");
      if (avatar === null) {
        box.innerHTML = personGlyph();
      } else {
        const image = document.createElement("img");
        image.className = "actor-avatar-image";
        for (const [attribute, value] of Object.entries({
          alt: "",
          width: "18",
          height: "18",
          loading: options.loading === "eager" ? "eager" : "lazy",
          decoding: "async",
          fetchpriority: "low",
          crossorigin: "anonymous",
          referrerpolicy: "no-referrer",
        })) {
          image.setAttribute(attribute, value);
        }
        image.addEventListener(
          "error",
          () => {
            box.replaceChildren();
            box.innerHTML = personGlyph();
          },
          { once: true },
        );
        image.setAttribute("src", avatar);
        box.append(image);
      }
      identity.append(box);
    }
    const label = document.createElement("strong");
    label.className = `actor-name${options.nameClass ? ` ${options.nameClass}` : ""}`;
    label.textContent = name;
    identity.append(label);
    return identity;
  }

  /**
   * The same identity as markup, for a view that writes its markup as text, as the Git
   * panel's commit summary does: the box with the person glyph, then the bold name. A view
   * with an avatar to show builds `actorIdentity`, whose image can give its box back to the
   * glyph if it fails.
   *
   * @param {string} name
   * @param {{className?: string, nameClass?: string}} [options]
   * @returns {string}
   */
  function actorIdentityHtml(name, options = {}) {
    return (
      `<span class="actor-identity${options.className ? ` ${escapeHtml(options.className)}` : ""}">` +
      `<span class="actor-avatar" aria-hidden="true">${personGlyph()}</span>` +
      `<strong class="actor-name${options.nameClass ? ` ${escapeHtml(options.nameClass)}` : ""}">` +
      `${escapeHtml(name)}</strong></span>`
    );
  }

  // A drawn age, the shell's one builder (`MetabrowserFormatters.ageLabel` in formatters.js):
  // its label in its freshness class, which alone sets its ink, after the call site's own
  // class, which places it (docs/design-system.md, "Age"). A plugin draws every age it shows
  // with these, so none can be drawn without its ink.

  /**
   * An age as an element, empty where the time is not known.
   * @param {number | null | undefined} secondsSinceEpoch
   * @param {MetabrowserAgeLabelOptions} [options]
   * @returns {HTMLSpanElement}
   */
  function ageLabel(secondsSinceEpoch, options) {
    return global.MetabrowserFormatters.ageLabel(global.document, secondsSinceEpoch, options);
  }

  /**
   * An age as markup, or "" where the time is not known.
   * @param {number | null | undefined} secondsSinceEpoch
   * @param {MetabrowserAgeLabelOptions} [options]
   * @returns {string}
   */
  function ageLabelHtml(secondsSinceEpoch, options) {
    return global.MetabrowserFormatters.ageLabelHtml(secondsSinceEpoch, options);
  }

  // A freshness class is one of the stylesheet's age-* classes, and a call site's own class
  // ends in "-age" instead; tests/test_age_single_source.py holds both, so telling an age again
  // can swap its freshness class and keep every other. Not a startup script's: only a view
  // that keeps its ages tells them again, and the startup scripts' budget had no room for it.
  const FRESHNESS_CLASS = /^age-/;

  /**
   * Tell a drawn age as of now, as a ticking or kept view does: its label, and its freshness
   * class in place of the one it had, its other classes kept. Returns its label.
   * @param {Element} element
   * @param {number | null | undefined} secondsSinceEpoch
   * @param {MetabrowserAgeOptions} [options]
   * @returns {string}
   */
  function retellAge(element, secondsSinceEpoch, options) {
    const { label, className } = global.MetabrowserFormatters.age(
      Number(secondsSinceEpoch) || 0,
      options,
    );
    if (element.textContent !== label) {
      element.textContent = label;
    }
    const had = element.getAttribute("class") ?? "";
    const kept = had.split(/\s+/).filter((name) => name !== "" && !FRESHNESS_CLASS.test(name));
    const wanted = [...kept, className].filter(Boolean).join(" ");
    if (had !== wanted) {
      element.setAttribute("class", wanted);
    }
    return label;
  }

  /**
   * An age's freshness tier, "sec" … "old", as a treemap's fill reads it, or null where the
   * time is not known: the drawn age's own tier, so a fill and a label never disagree.
   * @param {unknown} mtimeSeconds
   * @returns {MetabrowserAgeBucket | null}
   */
  function ageBucket(mtimeSeconds) {
    if (typeof mtimeSeconds !== "number") {
      return null;
    }
    const { className } = global.MetabrowserFormatters.age(mtimeSeconds);
    return className === "" ? null : /** @type {MetabrowserAgeBucket} */ (className.slice(4));
  }

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
      `${handler}${delegateOwnerAttribute()}>` +
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
      (global.MetabrowserIcons?.copy ?? "") +
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
    // Load more appends text nodes, which no parser reads, through the same function.
    const normalize = (/** @type {string} */ text) => lineAnchors.normalizeLineEndings(text);
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

  // Destination marks are view-phase presentation only: they grant no trust or URL
  // privileges. PR state stays with its plugin, which may supply a known icon.
  const githubHosts = new Set([
    "github.com",
    "www.github.com",
    "cli.github.com",
    "docs.github.com",
    "gist.github.com",
    "api.github.com",
  ]);
  const entityPath =
    /^\/[A-Za-z\d](?:[A-Za-z\d-]*[A-Za-z\d])?\/[A-Za-z\d_.-]+\/(issues|pull)\/[1-9]\d*(?:\/|$)/;
  /** @param {string | null} href @returns {"github" | "issue" | "pull" | null} */
  function githubDestination(href) {
    if (!href || /[\s\\]|\p{Cc}/u.test(href)) {
      return null;
    }
    let url;
    try {
      url = new URL(href, global.location.origin);
    } catch {
      return null;
    }
    if (
      !/^(https?:)$/.test(url.protocol) ||
      url.username ||
      url.password ||
      url.port ||
      !githubHosts.has(url.hostname)
    ) {
      return null;
    }
    const entity = url.hostname === "github.com" ? entityPath.exec(url.pathname) : null;
    if (
      entity === null ||
      (entity[1] === "pull" &&
        /^commits\/[a-f0-9]{40}\/?$/i.test(url.pathname.slice(entity[0].length)))
    ) {
      return "github";
    }
    return entity[1] === "issues" ? "issue" : "pull";
  }

  /* GitHub mark: Primer Octicons mark-github-16.svg, unchanged path, at
   * ea8e6bb79894cc7e85564ee9b53d86b418738d04 (2026-03-18).
   * https://github.com/primer/octicons/blob/ea8e6bb79894cc7e85564ee9b53d86b418738d04/icons/mark-github-16.svg
   * MIT License
   * Copyright (c) 2026 GitHub Inc.
   * Permission is hereby granted, free of charge, to any person obtaining a copy
   * of this software and associated documentation files (the "Software"), to deal
   * in the Software without restriction, including without limitation the rights
   * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
   * copies of the Software, and to permit persons to whom the Software is
   * furnished to do so, subject to the following conditions:
   * The above copyright notice and this permission notice shall be included in all
   * copies or substantial portions of the Software.
   * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
   * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
   * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
   * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
   * SOFTWARE.
   */
  const destinationGlyphs = {
    github:
      '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M6.766 11.328c-2.063-.25-3.516-1.734-3.516-3.656 0-.781.281-1.625.75-2.188-.203-.515-.172-1.609.063-2.062.625-.078 1.468.25 1.968.703.594-.187 1.219-.281 1.985-.281.765 0 1.39.094 1.953.265.484-.437 1.344-.765 1.969-.687.218.422.25 1.515.046 2.047.5.593.766 1.39.766 2.203 0 1.922-1.453 3.375-3.547 3.64.531.344.89 1.094.89 1.954v1.625c0 .468.391.734.86.547C13.781 14.359 16 11.53 16 8.03 16 3.61 12.406 0 7.984 0 3.563 0 0 3.61 0 8.031a7.88 7.88 0 0 0 5.172 7.422c.422.156.828-.125.828-.547v-1.25c-.219.094-.5.156-.75.156-1.031 0-1.64-.562-2.078-1.609-.172-.422-.36-.672-.719-.719-.187-.015-.25-.093-.25-.187 0-.188.313-.328.625-.328.453 0 .844.281 1.25.86.313.452.64.655 1.031.655s.641-.14 1-.5c.266-.265.47-.5.657-.656"/></svg>',
    /* Lucide 1.17.0: circle-dot.svg and git-pull-request.svg, neutral entity marks, and
     * circle-user-round.svg, the person in an actor identity's box.
     * arrow-right.svg and arrow-up-right.svg mark menu navigation.
     * https://github.com/lucide-icons/lucide/tree/896aba0d195a4fec38ad7c4a90d00cb3389ebfea/icons
     * ISC License
     * Copyright (c) 2026 Lucide Icons and Contributors
     * Permission to use, copy, modify, and/or distribute this software for any
     * purpose with or without fee is hereby granted, provided that the above
     * copyright notice and this permission notice appear in all copies.
     * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
     * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
     * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
     * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
     * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
     * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
     * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
     */
    issue:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="1"/></svg>',
    pull: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" x2="6" y1="9" y2="21"/></svg>',
    arrowRight: // Lucide `arrow-right`
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>',
    arrowUpRight:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>',
  };
  /** @type {WeakMap<HTMLElement, {node: HTMLElement, kind: string, supplied: Element | undefined}>} */
  const linkMarks = new WeakMap();
  /** The class of the span an image the page does not load becomes (inert_html.py). */
  const IMAGE_FALLBACK_CLASS = "mb-image-fallback";

  /**
   * Whether *anchor*'s whole content is images: a badge, or the fallback an image the page
   * does not load becomes, with no text of its own to put a mark after. github.com draws no
   * mark on one, and here it landed on a line of its own under the badges. The *mark* the
   * decorator put in it is not content.
   *
   * @param {HTMLElement} anchor
   * @param {HTMLElement | undefined} mark
   */
  function holdsImagesOnly(anchor, mark) {
    let images = 0;
    for (const child of Array.from(anchor.childNodes)) {
      if (child === mark) {
        continue;
      }
      if (child.nodeType === 3) {
        if ((child.nodeValue ?? "").trim() !== "") {
          return false;
        }
      } else if (child.nodeType === 1) {
        const element = /** @type {Element} */ (child);
        if (element.tagName !== "IMG" && !element.classList.contains(IMAGE_FALLBACK_CLASS)) {
          return false;
        }
        images += 1;
      }
    }
    return images > 0;
  }

  /** Decorate a final external destination without changing authored content or navigation.
   * Only the calling view may supply a state icon; document attributes are never read.
   * @template {HTMLElement} T
   * @param {T} anchor
   * @param {{icon?: Element | "github", position?: "before" | "after"}} [options]
   * @returns {T}
   */
  function decorateExternalLink(anchor, options = {}) {
    const destination =
      anchor.tagName === "A" ? githubDestination(anchor.getAttribute("href")) : null;
    const kind = destination === null ? null : options.icon === "github" ? "github" : destination;
    let mark = linkMarks.get(anchor);
    if (kind === null || holdsImagesOnly(anchor, mark?.node)) {
      mark?.node.remove();
      linkMarks.delete(anchor);
      return anchor;
    }
    const supplied = kind === "github" || options.icon === "github" ? undefined : options.icon;
    if (!mark || mark.node.parentNode !== anchor) {
      const node = anchor.ownerDocument.createElement("span");
      node.className = "external-link-icon";
      node.setAttribute("aria-hidden", "true");
      mark = { node, kind: "", supplied: undefined };
      linkMarks.set(anchor, mark);
      anchor.append(node);
    }
    if (mark.kind !== kind || mark.supplied !== supplied) {
      if (supplied) {
        mark.node.replaceChildren(supplied);
      } else {
        mark.node.innerHTML = destinationGlyphs[kind];
      }
      mark.node.setAttribute("data-external-kind", kind);
      mark.kind = kind;
      mark.supplied = supplied;
    }
    const leading = options.position === "before";
    mark.node.className = leading
      ? "external-link-icon external-link-icon-leading"
      : "external-link-icon";
    if (leading && anchor.firstChild !== mark.node) {
      anchor.insertBefore(mark.node, anchor.firstChild);
    } else if (!leading && anchor.lastChild !== mark.node) {
      anchor.append(mark.node);
    }
    return anchor;
  }

  /**
   * Two menu rows for an external URL supplied by the host or a trusted view. The
   * caller owns the menu's open state and focus, and may announce the copy result.
   *
   * @param {string} url
   * @param {{onActivate?: () => void, onCopyResult?: (result: "copied" | "failed") => void}} [options]
   * @returns {[HTMLButtonElement, HTMLAnchorElement]}
   */
  function externalLinkMenuItems(url, options = {}) {
    if (!/^https?:\/\//i.test(url)) {
      throw new TypeError("An external link menu needs an HTTP or HTTPS URL");
    }
    const doc = global.document;
    const copy = doc.createElement("button");
    renderLinkMenuItem(copy, "Copy Link", global.MetabrowserIcons?.copy ?? "");
    copy.setAttribute("type", "button");
    copy.addEventListener("click", () => {
      options.onActivate?.();
      const clipboard = global.navigator?.clipboard;
      if (!clipboard || typeof clipboard.writeText !== "function") {
        options.onCopyResult?.("failed");
        return;
      }
      clipboard.writeText(url).then(
        () => options.onCopyResult?.("copied"),
        () => options.onCopyResult?.("failed"),
      );
    });
    return [copy, externalLinkMenuItem(url, "Open in Browser", options.onActivate)];
  }

  /** @param {HTMLElement} item @param {string} text @param {string} glyph */
  function renderLinkMenuItem(item, text, glyph) {
    item.className = "menu-item";
    item.setAttribute("role", "menuitem");
    item.setAttribute("tabindex", "-1");
    const icon = global.document.createElement("span");
    icon.className = "menu-item-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = glyph;
    const label = global.document.createElement("span");
    label.className = "menu-item-label";
    label.textContent = text;
    item.append(icon, label);
    mb.ownDelegate(item);
  }

  /** @param {string} url @param {string} label @param {(() => void) | undefined} activate */
  function externalLinkMenuItem(url, label, activate) {
    const external = global.document.createElement("a");
    renderLinkMenuItem(external, label, destinationGlyphs.arrowUpRight);
    external.setAttribute("data-web-view", "external");
    external.setAttribute("href", url);
    external.setAttribute("target", "_blank");
    external.setAttribute("rel", "noopener");
    external.addEventListener("click", () => activate?.());
    return external;
  }

  /** Each counterpart provider's mark, drawn before its label. */
  /** @type {Record<string, string>} */
  const counterpartMarks = { github: destinationGlyphs.github };
  /** How long a copied link's confirmation stays under the button, as a code copy's does. */
  const COUNTERPART_COPIED_MS = 1500;
  let counterpartDestinationId = 0;

  /**
   * A page's external counterpart as a split button (docs/design-system.md, "View on
   * GitHub"): a link to the counterpart, its provider's mark and label, joined to a
   * chevron that opens a menu of Copy Link and Open in Browser. *counterpart* is what
   * `GET /api/counterpart` answers, so the provider supplies the label and the URL, and
   * another provider draws the same control.
   *
   * The root carries `data-view-on-<provider>`, which names the button. The links carry
   * the macOS app's contract, which names no site (mb-730z): the link
   * `data-web-view="open"`, and the menu's Open in Browser `data-web-view="external"`. In
   * a browser the link opens the page in a new tab; the app shows a plain click on it in a
   * web pane of its own, in a popover, when the page is on a site it knows. Nothing here
   * knows of the app.
   *
   * The menu is a menu button's: the chevron opens it with focus on its first item, the
   * arrow keys, Home, and End move among the items, and Escape, a second click on the
   * chevron, or an item closes it and gives focus back to the chevron, where a focused item
   * the menu hid would leave it nowhere (WebKit does not focus a clicked button). Tab or a
   * press outside closes it and leaves focus to the key or the press. A chord held with
   * Command, Control, or Option is left to the browser, but for Option-Tab, which closes
   * it as Tab does. A press, focus, or the window leaving it closes it too, through the
   * shared closing every menu has (`metabrowser.menus.dismissible`), whose listeners are
   * held only while a menu is open.
   *
   * Copy Link's result, "Link copied" or "Copy failed", shows under the button for
   * `COUNTERPART_COPIED_MS` in a status line, a polite live region a screen reader
   * announces, and on the chevron's tooltip.
   *
   * @param {MetabrowserCounterpart} counterpart
   * @returns {HTMLElement}
   */
  function counterpartButton(counterpart) {
    const doc = global.document;
    const hook = `data-view-on-${counterpart.provider}`;
    const root = doc.createElement("span");
    root.className = "counterpart";
    root.setAttribute(hook, "");
    const group = doc.createElement("span");
    group.className = "chip-group counterpart-group";
    group.dataset.layout = "joined";
    const open = doc.createElement("a");
    open.className = "chip counterpart-open";
    open.setAttribute("data-web-view", "open");
    open.setAttribute("href", counterpart.url);
    open.setAttribute("target", "_blank");
    open.setAttribute("rel", "noopener");
    open.dataset.tipText = counterpart.url.replace(/^https:\/\//, "");
    const mark = doc.createElement("span");
    mark.className = "counterpart-mark";
    mark.setAttribute("aria-hidden", "true");
    mark.innerHTML = counterpartMarks[counterpart.provider] ?? "";
    const label = doc.createElement("span");
    label.className = "counterpart-label";
    label.textContent = counterpart.label;
    open.append(mark, label);
    const more = doc.createElement("button");
    more.type = "button";
    more.className = "chip chip-menu-trigger counterpart-more disclosure-toggle";
    more.setAttribute("aria-haspopup", "menu");
    more.setAttribute("aria-expanded", "false");
    more.setAttribute("aria-label", `${counterpart.label}: Copy Link or Open in Browser`);
    const restingTip = "Copy Link or Open in Browser";
    more.dataset.tipText = restingTip;
    const caret = doc.createElement("span");
    caret.className = "chip-menu-caret";
    caret.setAttribute("aria-hidden", "true");
    caret.innerHTML = global.MetabrowserIcons?.toggle ?? "";
    more.append(caret);
    group.append(open, more);
    const menu = doc.createElement("div");
    menu.className = "menu counterpart-menu";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", counterpart.label);
    menu.hidden = true;
    const destination = doc.createElement("div");
    destination.className = "menu-link-url";
    const destinationId = `counterpart-url-${++counterpartDestinationId}`;
    destination.setAttribute("id", destinationId);
    destination.setAttribute("aria-hidden", "true");
    destination.textContent = counterpart.url;
    let copies = 0;
    const [copy, external] = externalLinkMenuItems(counterpart.url, {
      onActivate: () => close(true),
      onCopyResult(result) {
        const words = result === "copied" ? "Link copied" : "Copy failed";
        const copied = ++copies;
        status.dataset.result = result;
        status.textContent = words;
        more.dataset.tipText = words;
        global.setTimeout(() => {
          // A later copy's confirmation keeps its own time.
          if (copied === copies) {
            delete status.dataset.result;
            status.textContent = "";
            more.dataset.tipText = restingTip;
          }
        }, COUNTERPART_COPIED_MS);
      },
    });
    copy.dataset.counterpartAction = "copy";
    for (const item of [copy, external]) {
      item.setAttribute("aria-describedby", destinationId);
    }
    menu.append(destination, copy, external);
    // Empty until a copy, and in the page from the start: a live region made and filled at
    // once is not announced.
    const status = doc.createElement("span");
    status.className = "counterpart-status";
    status.setAttribute("role", "status");
    root.append(group, menu, status);

    /** @type {HTMLElement[]} */
    const items = [copy, external];
    /** @param {boolean} refocus whether focus goes back to the chevron */
    function close(refocus) {
      if (!menu.hidden) {
        menu.hidden = true;
        more.setAttribute("aria-expanded", "false");
      }
      dismissal?.closed();
      if (refocus) {
        more.focus();
      }
    }
    // It closes as every menu does (docs/design-system.md, "Every Menu Closes Alike").
    const dismissal = global.metabrowser.menus?.dismissible({
      name: "counterpart-menu",
      trigger: more,
      inside: (node) => menu.contains(node),
      isOpen: () => !menu.hidden,
      close: () => close(false),
    });
    /** @param {number} at the item to focus, from the end when negative */
    function show(at) {
      if (menu.hidden) {
        menu.hidden = false;
        more.setAttribute("aria-expanded", "true");
        dismissal?.opened();
      }
      items[((at % items.length) + items.length) % items.length].focus();
    }
    more.addEventListener("click", () => (menu.hidden ? show(0) : close(true)));
    // A chord is the browser's and the app's, Command-Up among them (mb-i1wy).
    more.addEventListener("keydown", (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        show(event.key === "ArrowDown" ? 0 : -1);
      }
    });
    menu.addEventListener("keydown", (event) => {
      // Tab leaves the menu, and so does Option-Tab, with which Safari moves focus: either
      // closes it and cancels nothing. Any other chord is the browser's and the app's.
      if (event.key === "Tab") {
        close(false);
        return;
      }
      if (event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const at = items.indexOf(/** @type {HTMLElement} */ (doc.activeElement));
      const moves = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: -1 };
      // Escape is the shared closing's, which gives focus back to the chevron.
      if (event.key in moves) {
        event.preventDefault();
        show(moves[/** @type {keyof typeof moves} */ (event.key)]);
      }
    });
    return root;
  }

  /** The page each corner last asked for, so a repaint of the same page asks once. */
  /** @type {WeakMap<Element, string>} */
  const counterpartAsked = new WeakMap();
  /**
   * The pages answered or asked for lately, most recent last: the last answer, whether no
   * drawing has used it yet (`fresh`), and the request in flight. Each answer serves one
   * drawing as it is: a page drawn again, by a return to it or a repaint with a new header,
   * draws its last answer with the header and asks again, unless that answer is fresh, as
   * one `prefetchCounterpart` asked for is. The button had come about 30 ms after the
   * header on a return to a file's page (median of 7, a mutation observer timing both,
   * Chrome 152, 2026-11-18).
   * @type {Map<string, {answer?: MetabrowserCounterpart | null, fresh?: boolean, asking?: Promise<MetabrowserCounterpart | null>}>}
   */
  const counterpartPages = new Map();
  /**
   * How many pages `counterpartPages` keeps: more than a session goes back to. An entry is
   * the address and the answer's three strings. In Node 24 on 2026-11-18, 64 entries of
   * typical addresses held 39 KB of heap, and 64 of the longest the server reads,
   * `MAX_PAGE_CHARS` (16 KiB), 2.1 MB, with every string flat and distinct.
   */
  const COUNTERPART_PAGES_MAX = 64;

  /** @param {string} page @returns {NonNullable<ReturnType<typeof counterpartPages.get>>} */
  function counterpartPage(page) {
    const kept = counterpartPages.get(page) ?? {};
    counterpartPages.delete(page);
    counterpartPages.set(page, kept);
    for (const oldest of counterpartPages.keys()) {
      if (counterpartPages.size <= COUNTERPART_PAGES_MAX) {
        break;
      }
      counterpartPages.delete(oldest);
    }
    return kept;
  }

  /**
   * Ask for *page*'s counterpart, once while a request is in flight.
   * @param {string} page
   * @returns {Promise<MetabrowserCounterpart | null>}
   */
  function askCounterpart(page) {
    const kept = counterpartPage(page);
    if (kept.asking === undefined) {
      const asking = (async () => {
        /** @type {{counterpart?: MetabrowserCounterpart | null} | null} */
        let answer = null;
        try {
          const response = await global.fetch(`/api/counterpart?page=${encodeURIComponent(page)}`);
          answer = response.ok ? await response.json() : null;
        } catch {
          // A server that went away draws no button; the next page asks again.
          answer = null;
        }
        const counterpart = answer?.counterpart ?? null;
        return counterpart !== null && /^https:\/\//.test(counterpart.url) ? counterpart : null;
      })();
      kept.asking = asking;
      // Registered before any drawing waits for the request, so it runs first.
      asking.then((counterpart) => {
        kept.answer = counterpart;
        kept.fresh = true;
        if (kept.asking === asking) {
          delete kept.asking;
        }
      });
    }
    return /** @type {Promise<MetabrowserCounterpart | null>} */ (kept.asking);
  }

  /**
   * Start asking for *page*'s counterpart before its header is drawn, so the answer can
   * arrive with it: the shell calls this as a file's or a folder's page starts loading.
   * `mountCounterpart` then waits for this request rather than making another.
   * @param {string} page
   */
  function prefetchCounterpart(page) {
    void askCounterpart(page);
  }

  /**
   * Put *counterpart*'s button in *corner*, keeping the one there when it is the same.
   * @param {Element} corner
   * @param {MetabrowserCounterpart | null} counterpart
   * @returns {HTMLElement | null}
   */
  function drawCounterpart(corner, counterpart) {
    const shown = /** @type {HTMLElement | null} */ (corner.querySelector(".counterpart"));
    if (counterpart === null) {
      corner.replaceChildren();
      return null;
    }
    const link = shown?.querySelector(".counterpart-open") ?? null;
    if (
      shown !== null &&
      link?.getAttribute("href") === counterpart.url &&
      shown.hasAttribute(`data-view-on-${counterpart.provider}`) &&
      link.textContent === counterpart.label
    ) {
      return shown;
    }
    const button = counterpartButton(counterpart);
    corner.replaceChildren(button);
    return button;
  }

  /**
   * Ask the server for *page*'s counterpart (`GET /api/counterpart`, the one place a
   * github.com URL is made) and put its button in *corner*, a header's
   * `.view-header-end`. *page* is the page's address as `location.pathname` spells it.
   * A page with none, or an answer that does not arrive, leaves the corner empty. Asked
   * again for the page a corner already asked for, it asks nothing; a corner asked for
   * another page before an answer lands drops that answer. A page answered before is
   * drawn at once, before this returns its promise, and asked again unless its answer is
   * fresh; the new answer replaces the button only when it differs. A request
   * `prefetchCounterpart` started is waited for, not repeated.
   *
   * @param {Element} corner
   * @param {string} page
   * @returns {Promise<HTMLElement | null>}
   */
  async function mountCounterpart(corner, page) {
    if (counterpartAsked.get(corner) === page) {
      return /** @type {HTMLElement | null} */ (corner.querySelector(".counterpart"));
    }
    counterpartAsked.set(corner, page);
    const kept = counterpartPages.get(page);
    if (kept?.answer !== undefined) {
      const drawn = drawCounterpart(corner, kept.answer);
      if (kept.fresh && kept.asking === undefined) {
        kept.fresh = false;
        counterpartPage(page);
        return drawn;
      }
    }
    const counterpart = await askCounterpart(page);
    if (counterpartAsked.get(corner) !== page) {
      return null;
    }
    const answered = counterpartPages.get(page);
    if (answered !== undefined) {
      answered.fresh = false;
    }
    return drawCounterpart(corner, counterpart);
  }

  /**
   * The tree of a change set's files, which the Pulls tab and a diff's Diff summary both
   * draw: static/changed-files-tree.js, the `changed-files-tree` on-demand bundle. Loaded
   * the first time a plugin asks, and once; a failed load rejects, and the next call tries
   * again.
   *
   * @returns {Promise<MetabrowserChangedFilesTree>}
   */
  // A change set's size line, "77 commits · 83 files changed · 2.3 MB compressed (14.0 MB raw
  // diff)", the line a page header gives its change set above its Diff summary
  // (docs/design-system.md, "Change Size Line"). The shared painter gives the counts
  // their emphasis and the byte values the Files navigation's size style. The words
  // and parentheses keep the line's weight and ink. Here, not in a startup
  // script: only a commit's or a pull request's page, and a commit's hover card, draw it.

  /**
   * A change set's size line in its parts: each group a count and its words, set apart by
   * muted dots, each kept with the group before it by a no-break space, so no line starts
   * with one, and said as a comma. A count `undefined` is left out and one null is "?"; the
   * size group is there once the pushed size is known.
   *
   * @param {MetabrowserChangeSizeInput} change
   * @returns {MetabrowserChangeSizeLine}
   */
  function changeSizeLine(change) {
    /** @param {number | null} count */
    const written = (count) => (count === null ? "?" : mb.formatInteger(count));
    /**
     * @param {number} bytes
     * @returns {{number: string, sizeStyle: "size" | "size size-large"}}
     */
    const bytePart = (bytes) => ({
      number: formatSize(bytes),
      sizeStyle: mb.sizeClass(bytes) ? "size size-large" : "size",
    });
    /** @type {Array<{parts: MetabrowserCountParts, words: string}>} */
    const groups = [];
    if (change.commits !== undefined) {
      const noun = change.commits === 1 ? "commit" : "commits";
      groups.push({
        parts: [{ number: written(change.commits) }, ` ${noun}`],
        words: `${written(change.commits)} ${noun}`,
      });
    }
    const files = change.files === 1 ? "file changed" : "files changed";
    groups.push({
      parts: [{ number: written(change.files) }, ` ${files}`],
      words: `${written(change.files)} ${files}`,
    });
    /** @type {MetabrowserCountParts} */
    let sizeParts = [];
    let tooltip = null;
    if (typeof change.pushedBytes === "number") {
      const pushed = bytePart(change.pushedBytes);
      sizeParts = [pushed, " compressed"];
      groups.push({ parts: [], words: `${pushed.number} compressed` });
      tooltip = `${pushed.number} compressed: what Git pushes for this change.`;
      if (typeof change.diffBytes === "number") {
        const diff = bytePart(change.diffBytes);
        sizeParts = [...sizeParts, " (", diff, " raw diff)"];
        groups.push({ parts: [], words: `${diff.number} raw diff` });
        tooltip += ` ${diff.number} raw diff: its patch, uncompressed.`;
      }
    }
    const separator = { separator: "·", spoken: ", " };
    const counts = groups.filter((group) => group.parts.length > 0).map((group) => group.parts);
    /** @type {MetabrowserCountParts} */
    const parts = [...counts, ...(sizeParts.length > 0 ? [sizeParts] : [])].flatMap((group, at) => [
      ...(at === 0 ? [] : ["\u00a0", separator, " "]),
      ...group,
    ]);
    const text = parts
      .map((part) =>
        typeof part === "string"
          ? part
          : "number" in part
            ? part.number
            : "separator" in part
              ? part.separator
              : "",
      )
      .join("");
    return {
      parts,
      sizeParts,
      text,
      label: groups.map((group) => group.words).join(", "),
      tooltip,
    };
  }

  /**
   * The line's counts, and its size in a `span.change-size-line-size` whose tooltip says
   * what each size is.
   * @param {MetabrowserChangeSizeLine} line
   */
  function sizeLineSplit(line) {
    const at = line.parts.length - line.sizeParts.length;
    return { counts: line.parts.slice(0, at), size: line.sizeParts };
  }

  /**
   * A change set's size line as the nodes of one `span.change-size-line`.
   * @param {MetabrowserChangeSizeLine} line
   * @returns {Array<Node | string>}
   */
  function changeSizeLineNodes(line) {
    const { counts, size } = sizeLineSplit(line);
    const element = document.createElement("span");
    element.className = "change-size-line";
    element.append(...mb.countPartsNodes(counts));
    if (size.length > 0) {
      const sized = document.createElement("span");
      sized.className = "change-size-line-size";
      if (line.tooltip !== null) {
        sized.dataset.tipText = line.tooltip;
      }
      sized.append(...mb.countPartsNodes(size));
      element.append(sized);
    }
    return [element];
  }

  /**
   * A change set's size line as markup, for a view that writes its markup as text, as the
   * Git panel's commit summary does.
   * @param {MetabrowserChangeSizeLine} line
   * @returns {string}
   */
  function changeSizeLineHtml(line) {
    const { counts, size } = sizeLineSplit(line);
    const paint = global.MetabrowserFormatters.countPartsHtml;
    const tip = line.tooltip === null ? "" : ` data-tip-text="${escapeHtml(line.tooltip)}"`;
    return (
      `<span class="change-size-line">${paint(counts)}` +
      (size.length > 0 ? `<span class="change-size-line-size"${tip}>${paint(size)}</span>` : "") +
      "</span>"
    );
  }

  // Limit how long a view waits to localize links before rendering. In nine cold loads
  // of a checkout's README from 127.0.0.1 in headless Chromium 152 on 2026-11-26, the asset
  // took 4 to 25 ms and always arrived before the Markdown request started. On 2026-11-27,
  // with the link card in a bundle of its own, 40 cold loads of a checkout's Markdown file
  // in headless Chrome 158 waited medians of 23.1 and 24.7 ms, at most 31.6 (server.py,
  // `repository-links`, has the measurement). The limit lets every surface render if that
  // optional request stalls.
  const REPOSITORY_LINKS_WAIT_MS = 250;

  /** @type {Promise<MetabrowserRepositoryLinksRuntime | null> | null} */
  let repositoryLinksWait = null;

  /**
   * The link resolver for a page with a GitHub repository's identity. All views join one
   * load and stop waiting at the same deadline. A stalled request stays in flight, so a
   * later view can use the resolver once installed. A failed request can be retried.
   *
   * @returns {Promise<MetabrowserRepositoryLinksRuntime | null>}
   */
  function loadRepositoryLinks() {
    if (!mb.repository) {
      return Promise.resolve(null);
    }
    if (global.MetabrowserRepositoryLinks) {
      return Promise.resolve(global.MetabrowserRepositoryLinks);
    }
    repositoryLinksWait ??= new Promise((resolve) => {
      const deadline = setTimeout(() => resolve(null), REPOSITORY_LINKS_WAIT_MS);
      void Promise.resolve()
        .then(() => mb.ensureAsset("repository-links"))
        .then(
          () => resolve(global.MetabrowserRepositoryLinks ?? null),
          (error) => {
            repositoryLinksWait = null;
            console.warn("metabrowser: repository links are unavailable", error);
            resolve(null);
          },
        )
        .finally(() => clearTimeout(deadline));
    });
    return repositoryLinksWait;
  }

  // ── Link cards, until their bundle loads ──────────────────────
  //
  // Every link in authored text has its link card on every page, whatever repository it
  // serves (docs/design-system.md, "Tooltips on Links"). The card, its registry, and its
  // providers are the `link-previews` bundle, code that runs only once a pointer rests on a
  // registered link, so the page loads it at the first such rest (server.py has the
  // measurement). Until then a surface's links are kept here by identity, with one
  // delegated listener per root, and only while the page keeps the root, since a page read
  // by touch or keyboard never loads it. The first `pointerover` of one, not from a touch,
  // loads the bundle, whose registry then takes every link and the rest that load began, as
  // old as the load took (`rest` in static/link-previews.js), so that rest shows its card; a
  // press or a focus meanwhile ends it. From then on each call goes straight to the
  // registry. A bundle that does not load leaves every link as it was, its author's title
  // given back, with one warning. tests/dom/link-preview-loader-session.js runs this file
  // whole.

  const LINK_PREVIEWS_BUNDLE = "link-previews";
  /** Bounds URL parsing work for one link, as the resolver's `MAX_URL_LENGTH` does. */
  const MAX_OUTSIDE_URL_LENGTH = 16 * 1024;

  /**
   * @typedef {{target: MetabrowserLinkPreviewTarget, options: {authorTitle?: string | null}}} PendingLink
   * @typedef {{links: Map<Element, PendingLink>, over: (event: Event) => void, out: (event: Event) => void, ref: WeakRef<Element>}} PendingRoot
   * @typedef {{root: Element, anchor: Element, since: number, ended: boolean}} PendingRest
   */

  /** @type {"waiting" | "loading" | "loaded" | "failed"} */
  let linkCards = "waiting";
  /** Each root's links, and its listeners, until the bundle loads. @type {WeakMap<Element, PendingRoot>} */
  const pendingRoots = new WeakMap();
  /** Those roots, to hand over. @type {Set<WeakRef<Element>>} */
  const pendingRootRefs = new Set();
  const collectedRoots = new FinalizationRegistry((/** @type {WeakRef<Element>} */ ref) =>
    pendingRootRefs.delete(ref),
  );
  /** @type {WeakMap<Element, Element>} */
  const pendingRootOf = new WeakMap();
  /** The pointer's rest on a registered link while the bundle loads. @type {PendingRest | null} */
  let pendingRest = null;

  function linkCardRegistry() {
    return linkCards === "loaded" ? (global.MetabrowserLinkPreviews ?? null) : null;
  }

  /**
   * Give *anchor*, a link of *root* that opens *target*, its link card, in place of any it
   * had: a page here (a `view` or `route` answer, or a rendered diff's `view-head` link), or
   * one on another site (`{kind: "external", url}`). *root* is the element whose cards its
   * surface puts away together (`disposePreviews`). The surface takes *authorTitle*, its
   * author's title, off the link when this answers that the link has a card: before the
   * bundle loads, whether the target is one a card is about (`namesLinkCard`). A link the
   * registry then turns down, or every link when it cannot load, gets that title back.
   *
   * @param {Element} root
   * @param {Element} anchor
   * @param {MetabrowserLinkPreviewTarget} target
   * @param {{authorTitle?: string | null}} [options]
   * @returns {boolean}
   */
  function previewLink(root, anchor, target, options = {}) {
    const registry = linkCardRegistry();
    if (registry !== null) {
      return registry.register(root, anchor, target, mb, options);
    }
    if (linkCards === "failed" || !namesLinkCard(target)) {
      forgetPreview(anchor);
      return false;
    }
    const previous = pendingRootOf.get(anchor);
    if (previous !== undefined && previous !== root) {
      pendingRoots.get(previous)?.links.delete(anchor);
      if (pendingRest?.anchor === anchor) {
        pendingRest.root = root;
      }
    }
    pendingRootOf.set(anchor, root);
    listenBeforeCards(root).links.set(anchor, { target, options });
    return true;
  }

  /** *anchor* has no card any more. @param {Element} anchor */
  function forgetPreview(anchor) {
    const registry = linkCardRegistry();
    if (registry !== null) {
      registry.forget(anchor);
      return;
    }
    const root = pendingRootOf.get(anchor);
    if (root === undefined) {
      return;
    }
    pendingRootOf.delete(anchor);
    pendingRoots.get(root)?.links.delete(anchor);
    if (pendingRest?.anchor === anchor) {
      pendingRest = null;
    }
  }

  /**
   * Forget the cards of *root*'s links, and put away the one it shows and no other
   * surface's, as a surface does with a text it replaces or disposes.
   *
   * @param {Element} root
   */
  function disposePreviews(root) {
    const registry = linkCardRegistry();
    if (registry !== null) {
      registry.dispose(root);
      return;
    }
    const state = pendingRoots.get(root);
    if (state === undefined) {
      return;
    }
    pendingRoots.delete(root);
    pendingRootRefs.delete(state.ref);
    root.removeEventListener("pointerover", state.over);
    root.removeEventListener("pointerout", state.out);
    for (const anchor of state.links.keys()) {
      pendingRootOf.delete(anchor);
    }
    if (pendingRest?.root === root) {
      pendingRest = null;
    }
  }

  /**
   * Whether a card is about *target*, as far as the registry's reading (`subject` in
   * static/link-previews.js) can be told without it: an in-app answer, or an address on
   * another site (`outsideAddress`), so a mail link has none.
   *
   * @param {unknown} target
   */
  function namesLinkCard(target) {
    if (!target || typeof target !== "object") {
      return false;
    }
    const { kind, url } = /** @type {{kind?: unknown, url?: unknown}} */ (target);
    if (kind === "view" || kind === "view-head" || kind === "route") {
      return true;
    }
    return kind === "external" && outsideAddress(url) !== null;
  }

  /**
   * Where a link to another site goes, as the browser follows it: *url* read against the
   * page's address, if that is an `http` or `https` address off the page's origin, so a
   * mail link, and `http:x.md` on an `http` page, have none. The card reads it too
   * (`outsideSubject` in static/link-previews.js), so the two cannot disagree.
   *
   * @param {unknown} url
   * @returns {URL | null}
   */
  function outsideAddress(url) {
    if (typeof url !== "string" || url.length > MAX_OUTSIDE_URL_LENGTH) {
      return null;
    }
    try {
      const page = new URL(global.document.baseURI);
      const address = new URL(url, page);
      return /^https?:$/.test(address.protocol) && address.origin !== page.origin ? address : null;
    } catch (_error) {
      return null;
    }
  }
  global.MetabrowserOutsideLinks = Object.freeze({ address: outsideAddress });

  /** @param {Element} root @returns {PendingRoot} */
  function listenBeforeCards(root) {
    let state = pendingRoots.get(root);
    if (state === undefined) {
      state = {
        links: new Map(),
        over: (event) => pointerOverBeforeCards(root, event),
        out: (event) => pointerOutBeforeCards(root, event),
        ref: new WeakRef(root),
      };
      pendingRoots.set(root, state);
      pendingRootRefs.add(state.ref);
      collectedRoots.register(root, state.ref);
      root.addEventListener("pointerover", state.over);
      root.addEventListener("pointerout", state.out);
    }
    return state;
  }

  /**
   * The registered link of *root* at or above *node*, or null.
   * @param {Element} root
   * @param {EventTarget | null} node
   * @returns {Element | null}
   */
  function pendingAnchorOf(root, node) {
    const links = pendingRoots.get(root)?.links;
    for (let at = /** @type {Node | null} */ (node); links && at && at !== root; ) {
      if (links.has(/** @type {Element} */ (at))) {
        return /** @type {Element} */ (at);
      }
      at = at.parentNode;
    }
    return null;
  }

  /**
   * A rest begins on the registered link the pointer moved onto, and loads the bundle; a
   * touch is a tap that opens the link.
   * @param {Element} root
   * @param {Event} event
   */
  function pointerOverBeforeCards(root, event) {
    if (/** @type {PointerEvent} */ (event).pointerType === "touch") {
      return;
    }
    const anchor = pendingAnchorOf(root, event.target);
    if (anchor === null || pendingRest?.anchor === anchor) {
      return;
    }
    pendingRest = { root, anchor, since: global.performance.now(), ended: false };
    loadLinkCards();
  }

  /**
   * The rest ends when the pointer leaves its link for anything outside it.
   * @param {Element} root
   * @param {Event} event
   */
  function pointerOutBeforeCards(root, event) {
    const rest = pendingRest;
    if (rest === null || rest.root !== root) {
      return;
    }
    const related = /** @type {PointerEvent} */ (event).relatedTarget;
    if (related !== null && rest.anchor.contains(/** @type {Node} */ (related))) {
      return;
    }
    if (pendingAnchorOf(root, event.target) === rest.anchor) {
      pendingRest = null;
    }
  }

  /** A press or a focus while the bundle loads: that rest shows no card. */
  function endRestBeforeCards() {
    if (pendingRest !== null) {
      pendingRest.ended = true;
    }
  }

  /** Load the bundle, once, and hand it every link registered here. */
  function loadLinkCards() {
    if (linkCards !== "waiting") {
      return;
    }
    linkCards = "loading";
    const page = global.document;
    page.addEventListener("pointerdown", endRestBeforeCards, true);
    page.addEventListener("focusin", endRestBeforeCards, true);
    const listened = () => {
      page.removeEventListener("pointerdown", endRestBeforeCards, true);
      page.removeEventListener("focusin", endRestBeforeCards, true);
    };
    void Promise.resolve()
      .then(() => mb.ensureAsset(LINK_PREVIEWS_BUNDLE))
      .then(() => {
        const registry = global.MetabrowserLinkPreviews;
        if (registry === undefined) {
          throw new Error(`the ${LINK_PREVIEWS_BUNDLE} bundle installed no registry`);
        }
        return registry;
      })
      .then(
        (registry) => {
          listened();
          handOverLinkCards(registry);
        },
        (error) => {
          listened();
          console.warn("metabrowser: link cards are unavailable", error);
          handOverLinkCards(null);
        },
      );
  }

  /**
   * Hand every link of a root the page still keeps to *registry*, or, with none, since the
   * bundle did not load, give each its title back.
   * @param {MetabrowserLinkPreviewsRuntime | null} registry
   */
  function handOverLinkCards(registry) {
    const rest = pendingRest;
    const refs = Array.from(pendingRootRefs);
    pendingRest = null;
    pendingRootRefs.clear();
    linkCards = registry ? "loaded" : "failed";
    for (const ref of refs) {
      const root = ref.deref();
      const state = root && pendingRoots.get(root);
      if (!root || !state) {
        continue;
      }
      pendingRoots.delete(root);
      root.removeEventListener("pointerover", state.over);
      root.removeEventListener("pointerout", state.out);
      for (const [anchor, link] of state.links) {
        pendingRootOf.delete(anchor);
        if (!registry?.register(root, anchor, link.target, mb, link.options)) {
          giveTitleBack(anchor, link);
        }
      }
    }
    if (registry && rest !== null) {
      registry.rest(rest.anchor, {
        elapsed: global.performance.now() - rest.since,
        ended: rest.ended,
      });
    }
  }

  /**
   * A link with no card after all keeps its author's title, which its surface took off it.
   * @param {Element} anchor
   * @param {PendingLink} link
   */
  function giveTitleBack(anchor, link) {
    const title = link.options.authorTitle;
    if (typeof title === "string" && title !== "" && !anchor.hasAttribute("title")) {
      anchor.setAttribute("title", title);
    }
  }

  function loadChangedFilesTree() {
    return mb.ensureAsset("changed-files-tree").then(() => {
      const tree = global.MetabrowserChangedFilesTree;
      if (tree === undefined) {
        throw new Error("metabrowser.loadChangedFilesTree: the bundle installed no tree");
      }
      return tree;
    });
  }

  /**
   * An on-demand module bundle's absolute URL, or null for a name that is not one: what a
   * frame of a plugin's own imports to run the module in that frame's realm, where the
   * namespace `ensureModule` returns cannot reach (markdown/diagram-frame.js). Here and not
   * in the startup scripts, asset-loader.js among them, since only a view that draws such
   * a frame asks; it reads a bundle as `ensureModule` does, which
   * tests/dom/markdown-diagram-frame-session.js checks shape by shape.
   *
   * @param {string} name
   * @returns {string | null}
   */
  function moduleUrl(name) {
    // A module bundle is one `{module: url}` entry (asset-loader.js, `ensureModule`).
    const entries = /** @type {unknown} */ (global.METABROWSER_ASSET_BUNDLES?.[name]);
    const entry = Array.isArray(entries) && entries.length === 1 ? entries[0] : null;
    const url =
      entry && typeof entry === "object" && typeof entry.module === "string" ? entry.module : "";
    return url ? new URL(url, global.location.href).href : null;
  }

  Object.assign(mb, {
    actorIdentity,
    actorIdentityHtml,
    changeSizeLine,
    changeSizeLineHtml,
    changeSizeLineNodes,
    counterpartButton,
    decorateExternalLink,
    disposePreviews,
    externalLinkMenuItems,
    forgetPreview,
    loadChangedFilesTree,
    loadRepositoryLinks,
    mountCounterpart,
    prefetchCounterpart,
    previewLink,
    refChipHtml,
    refChip,
    mergeRefs,
    mountRefMenus,
    mountRefCopies: mountRefMenus,
    ageBucket,
    ageLabel,
    ageLabelHtml,
    retellAge,
    highlightSyntax: highlightSyntax,
    isLargeTextPreview: isLargeTextPreview,
    langForExtension: langForExtension,
    langForPath: langForPath,
    partialNoticeHtml: partialNoticeHtml,
    renderSourceView: renderSourceView,
    renderTextLoadMoreFooter: renderTextLoadMoreFooter,
    renderTextTruncationWarning: renderTextTruncationWarning,
    wrapWithCopy: wrapWithCopy,
    moduleUrl,
  });
})(/** @type {Window & typeof globalThis} */ (typeof window !== "undefined" ? window : globalThis));
