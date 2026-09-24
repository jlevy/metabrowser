// Line numbers and GitHub-style line anchors in source views.
//
// A source view shows a gutter of line numbers beside its code. A `/view/` address
// whose fragment is `#L10`, `#L10-L20`, or `#L10C5-L20C8` highlights those lines, and
// scrolls the first one into view once the file is open and whenever the fragment
// changes. Clicking a line number anchors that line, and shift-clicking extends the
// anchor to a range; either replaces the address through the navigation controller,
// so the address bar, and a copy of it, carries the anchor. Columns are kept in the
// address but highlight whole lines.
//
// The fragment is the only state: `describe` turns it and what the view has loaded
// into what to highlight and what to say, and `nextFragment` turns a click into the
// next fragment. Neither touches the DOM. The gutter and the highlight are painted
// by CSS from two custom properties, in line-height units, so this file measures
// nothing except where a click landed. A large file shows only its first part until
// Load more; a line past that part is reported as not loaded rather than guessed at,
// and becomes the anchor once Load more reaches it.
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
   *   target: HTMLElement | null,
   *   path: string,
   *   loaded: LoadedText,
   *   navigation: Navigation | null,
   *   applied: string,
   *   clicked: string,
   *   state: AnchorState,
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
   * node, hidden from assistive technology because the code already has the lines.
   *
   * @param {string} text
   */
  function gutterHtml(text) {
    return `<span class="source-line-numbers" aria-hidden="true">${gutterText(countLines(text))}</span>`;
  }

  // ── DOM glue ──────────────────────────────────────────────────────────────

  /** @type {Set<View>} */
  const views = new Set();

  /** @param {string} path */
  function filePath(path) {
    return path.endsWith("/") ? path.slice(0, -1) : path;
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
    paintHighlight(view);
    paintNotice(view);
    if (scroll && view.target) {
      view.target.scrollIntoView({ block: "center", inline: "nearest" });
    }
  }

  /**
   * @param {View} view
   * @param {MouseEvent} event
   */
  function handleGutterClick(view, event) {
    if (event.button !== 0 || event.target !== view.gutter) {
      return;
    }
    const style = view.gutter.ownerDocument.defaultView?.getComputedStyle(view.gutter);
    const lineHeight = Number.parseFloat(style?.lineHeight || "");
    const line = lineAt(event.offsetY, lineHeight, view.loaded.lines);
    if (!line) {
      return;
    }
    const fragment = nextFragment(view.applied, line, event.shiftKey);
    apply(view, fragment, false);
    const target = currentTarget(view);
    if (!target || !view.navigation) {
      return;
    }
    // The address changes through the navigation controller, which then delivers
    // the fragment back to this view; a clicked line stays where the reader is.
    view.clicked = fragment;
    const next = target.query
      ? { path: target.path, query: target.query, fragment }
      : { path: target.path, fragment };
    void view.navigation.open(next, { replace: true }).catch((error) => {
      view.clicked = "";
      console.warn("Could not put the line anchor in the address", error);
    });
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
    const code = pre?.querySelector("code");
    if (!pre || !gutter || !code) {
      return;
    }
    /** @type {View} */
    const view = {
      pre,
      gutter,
      notice: null,
      target: null,
      path: options.path,
      loaded: Object.freeze({
        lines: countLines(code.textContent || ""),
        truncated: options.truncated,
      }),
      navigation: options.navigation,
      applied: "",
      clicked: "",
      state: describe("", { lines: 0, truncated: false }),
    };
    views.add(view);
    // A shift-click would otherwise extend the page's text selection to the gutter.
    gutter.addEventListener("mousedown", (event) => {
      if (event.shiftKey) {
        event.preventDefault();
      }
    });
    gutter.addEventListener("click", (event) => handleGutterClick(view, event));
    apply(view, currentTarget(view)?.fragment || "", false);
  }

  /**
   * Bring the views under `root` in line with text Load more appended: renumber the
   * gutter and reapply the anchor, scrolling to it if it has just been reached.
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
      const code = view.pre.querySelector("code");
      const lines = countLines(code?.textContent || "");
      if (lines !== view.loaded.lines) {
        const numbers = view.gutter.firstChild;
        if (numbers && numbers.nodeType === 3) {
          numbers.nodeValue = gutterText(lines);
        } else {
          view.gutter.prepend(view.pre.ownerDocument.createTextNode(gutterText(lines)));
        }
      }
      const reached = view.state.status === "not-loaded";
      view.loaded = Object.freeze({ lines, truncated: !!loaded.content_truncated });
      apply(view, view.applied, reached);
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
        const own = fragment === view.clicked;
        view.clicked = "";
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
    lineAt,
    mount,
    nextFragment,
    parse,
    refresh,
  });
})(/** @type {Window & typeof globalThis} */ (typeof window !== "undefined" ? window : globalThis));
