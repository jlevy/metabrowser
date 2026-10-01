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
// What stays in plugin-sdk.js is what the shell needs to start, and the syntax service,
// whose record of the optional-assets event has to exist before that event fires.
//
// Measured 2026-10-01 in Chrome 152: these were 3,572 of plugin-sdk.js's 22,308
// compressed bytes. See explorations/performance-loop/experiments/exp-037.

((global) => {
  const mb = global.metabrowser;
  if (!mb || typeof mb.registerView !== "function") {
    throw new Error("plugin-sdk-views.js requires window.metabrowser");
  }
  const { delegateOwnerAttribute, escapeHtml, formatSize } = mb;

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
    const large = mb.isLargeTextPreview(data);
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
    langForExtension: langForExtension,
    langForPath: langForPath,
    partialNoticeHtml: partialNoticeHtml,
    renderSourceView: renderSourceView,
    renderTextLoadMoreFooter: renderTextLoadMoreFooter,
    renderTextTruncationWarning: renderTextTruncationWarning,
    wrapWithCopy: wrapWithCopy,
  });
})(/** @type {Window & typeof globalThis} */ (typeof window !== "undefined" ? window : globalThis));
