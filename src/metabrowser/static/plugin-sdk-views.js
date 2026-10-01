// View-phase SDK helpers: what a view's renderer calls, and the first tree does not.
//
// plugin-sdk.js is a startup script, so every byte of it is fetched before the first
// tree paints. These helpers build a view's markup -- the Source surface, the copy
// wrapper, the partial-content notice -- and nothing runs them until a view renders.
// They load as the `sdk-views` bundle instead: `loadViewComposition` fetches it beside
// the view compositor, and `loadPluginsForKind` waits for it before it loads a plugin,
// so every one of them is on `window.metabrowser` before any plugin module evaluates
// or any renderer runs. A plugin sees the same SDK it always did.
//
// The syntax service is here too: nothing asks for a token until a view shows code.
//
// Measured 2026-10-01 in Chrome 152: all of this was 5,632 of plugin-sdk.js's 22,308
// compressed bytes as a startup script. See
// explorations/performance-loop/experiments/exp-037.

((global) => {
  const mb = global.metabrowser;
  if (!mb || typeof mb.registerView !== "function") {
    throw new Error("plugin-sdk-views.js requires window.metabrowser");
  }
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
    // Line numbers and #L anchors: source-line-anchors.js is fetched with the view
    // compositor, which the shell waits for before it runs any renderer, so the
    // gutter is part of a Source view's first paint without being part of the shell's.
    // The HTML parser turns CR and CRLF into LF, so the gutter counts the same text.
    const lineAnchors = global.MetabrowserSourceLineAnchors;
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
