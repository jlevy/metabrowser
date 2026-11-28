// A file's and a folder's view header (docs/design-system.md, "View Headers"): the rows
// renderFile in app.js draws above a view, and the folder line its live refresh rewrites.
//
// On demand, as the `view-header` bundle in server.py, not a startup script: a header is
// drawn only once loadViewComposition in app.js has fetched this beside the compositor
// and the SDK's view helpers, so a folder's first tree never waits for it. The builders
// work through the shell's own helpers, which app.js passes to `create`, so a size, a
// count, an age, and an icon here are the tree rows' own.

(() => {
  if (window.MetabrowserViewHeader) {
    return;
  }

  // Every label a run's status badge shows, Running, Live, Done, Failed, and Run ended,
  // each a badge's box of no height beside the badge in its slot: the slot is the widest
  // label's width, so a label that changes in place moves nothing (styles.css,
  // `.file-header-badge-slot`). flagRunEndedBadge in app.js changes the label.
  const RUN_STATUS_SIZERS = ["Running", "Live", "Done", "Failed", "Run ended"]
    .map(
      (label) =>
        `<span class="file-header-badge file-header-badge-sizer" aria-hidden="true">${label}</span>`,
    )
    .join("");

  /**
   * The view header's builders over the shell's helpers.
   * @param {MetabrowserViewHeaderShell} shell
   * @returns {Readonly<MetabrowserViewHeaderBuilders>}
   */
  function create(shell) {
    const {
      esc,
      servedRoot,
      servedRootName,
      ownedControlAttr,
      mirrorHeading,
      getFileIcon,
      getLogicalName,
      sizeHtml,
      countHtml,
      formatAge,
      activeFiles,
    } = shell;

    /**
     * A view header's eyebrow address: the served root's whole address, one crumb to the
     * root, then a crumb per folder above the item, whose name is the title, each crumb
     * followed by a separator that is text; at the root, the directory that holds it,
     * dimmed. The folders above the served root are not open, so the address is the root's
     * one crumb rather than a crumb each. A crumb's tip is its own text, shown only while it
     * is cut short (`tipAddsInformation` in app.js).
     * @param {string} path served-root-relative path; "" is the root itself
     */
    function headerEyebrowAddressHtml(path) {
      const root = servedRoot();
      const segments = path ? path.split("/") : [];
      // <bdi> isolates the path from the start-truncation direction of .file-header-root
      // and .folder-crumb-root.
      if (segments.length === 0) {
        const parent = esc(servedRootParent(root));
        return (
          (parent ? `<span class="file-header-root"><bdi>${parent}</bdi></span>` : "") +
          mirrorHeading("note")
        );
      }
      const separator = '<span class="folder-crumb-sep">/</span>';
      const address = esc(root);
      let html = `<button type="button" class="folder-crumb folder-crumb-root" data-nav-dir=""${ownedControlAttr()} data-tip-text="${address}"><bdi>${address}</bdi></button>${separator}`;
      let walked = "";
      for (let i = 0; i < segments.length - 1; i++) {
        walked = walked ? `${walked}/${segments[i]}` : segments[i];
        const name = esc(window.MetabrowserNavigationRoute.displayPath(segments[i]));
        html += `<button type="button" class="folder-crumb" data-nav-dir="${esc(walked)}"${ownedControlAttr()} data-tip-text="${name}">${name}</button>${separator}`;
      }
      return html + mirrorHeading("note");
    }

    /**
     * The directory holding the served root, "~/a" for "~/a/b"; none for a mirror's name.
     * @param {string} root
     */
    function servedRootParent(root) {
      const trimmed = root.replace(/\/+$/, "");
      const cut = trimmed.lastIndexOf("/");
      return cut > 0 ? trimmed.slice(0, cut) : cut === 0 ? "/" : "";
    }

    /**
     * A view header's title: the item's name, or the served root's, as a link card names
     * the root (`rootName` in static/link-previews.js), or `/` where it has none.
     * @param {string} path
     */
    function viewHeaderName(path) {
      if (path) {
        const segments = path.split("/");
        return window.MetabrowserNavigationRoute.displayPath(segments[segments.length - 1]);
      }
      return servedRootName() || "/";
    }

    /** The eyebrow's Up: the item's folder, or disabled in place at the root. @param {string} path */
    function viewHeaderUpHtml(path) {
      const segments = path ? path.split("/") : [];
      const parent = segments.slice(0, -1).join("/");
      const label = parent
        ? `${window.MetabrowserNavigationRoute.displayPath(segments[segments.length - 2])}/`
        : "/";
      const attrs = path
        ? `data-tip-text="Open ${esc(label)}" aria-label="Open parent folder ${esc(label)}" data-nav-dir="${esc(parent)}"${ownedControlAttr()}`
        : 'data-tip-text="No parent folder" aria-label="No parent folder" disabled';
      return `<button type="button" class="icon-btn folder-up" ${attrs}><span class="parent-nav-arrow" aria-hidden="true">↑</span></button>`;
    }

    /**
     * A metadata line's items, each after a muted dot but the first and one box with it, so
     * a line too wide for its row wraps both whole (`.view-header-line`); an empty item is
     * left out.
     * @param {string[]} items
     */
    function viewHeaderItemsHtml(items) {
      return items
        .filter(Boolean)
        .map(
          (item, index) =>
            '<span class="view-header-item">' +
            (index === 0
              ? ""
              : '<span class="summary-punctuation view-header-sep" aria-hidden="true">·</span>') +
            item +
            "</span>",
        )
        .join("");
    }

    /**
     * One view header (docs/design-system.md, "View Headers"): the eyebrow, which an empty
     * one leaves out; the heading row: the icon, then the title with the metadata line right
     * after it; and the header's corner. The name is whole, never cut, so it has no tooltip:
     * a name too long for the row wraps, and the line with it. The corner is placed at the
     * end of the title's first line, on its baseline, and follows the heading row in the
     * reading order. On a page whose repository is on github.com it is marked
     * `data-counterpart`, so the title's first line leaves it room for the View on GitHub
     * button the shell then asks for (`mountCounterpart`, plugin-sdk-views.js).
     * @param {MetabrowserViewHeaderParts} parts
     */
    function viewHeaderHtml(parts) {
      const counterpart = window.METABROWSER_REPOSITORY_CONTEXT ? " data-counterpart" : "";
      const iconId = parts.iconId ? ` data-page-icon="${esc(parts.iconId)}"` : "";
      return (
        `<div class="file-header view-header${parts.className ? ` ${parts.className}` : ""}" data-path="${esc(parts.path)}" data-kbd-badge-anchor>` +
        `<div class="view-header-eyebrow">${parts.eyebrow}</div>` +
        '<div class="view-header-heading">' +
        `<span class="view-header-icon file-identity-icon${parts.iconClass ? ` ${parts.iconClass}` : ""}"${parts.iconStyle ? ` style="${esc(parts.iconStyle)}"` : ""}${iconId} aria-hidden="true">${parts.iconHtml}</span>` +
        '<div class="view-header-title-group">' +
        `<h1 class="view-header-title page-heading">${esc(parts.title)}</h1>` +
        `<div class="view-header-line page-header-line">${parts.line}</div>` +
        "</div>" +
        "</div>" +
        `<span class="view-header-end"${counterpart}></span>` +
        "</div>"
      );
    }

    /** A file's or a folder's eyebrow: Up, then the address of the item's folder. @param {string} path */
    function viewHeaderEyebrowHtml(path) {
      return (
        viewHeaderUpHtml(path) +
        `<span class="file-header-path folder-breadcrumb">${headerEyebrowAddressHtml(path)}</span>`
      );
    }

    /**
     * The glyph a folder's header leads with: for the root, the kind mark the navigation's
     * heading already holds (the server wrote it, `.header-root-kind`), so the root is drawn
     * as the kind of root it is wherever its name is, and for any other folder the ordinary
     * folder's. A page with no such mark draws the ordinary folder.
     * @param {string} path served-root-relative path; "" is the root itself
     */
    function folderGlyphHtml(path) {
      const ordinary = window.MetabrowserIcons?.folder || "";
      if (path !== "" || typeof document === "undefined") {
        return ordinary;
      }
      return document.querySelector("#header-root-kind > svg")?.outerHTML ?? ordinary;
    }

    /**
     * A folder's view header: eyebrow, folder icon and name, and its aggregate line.
     * @param {Parameters<MetabrowserViewHeaderBuilders["renderFolderHeader"]>[0]} data the folder's envelope
     */
    function renderFolderHeader(data) {
      const path = typeof data.path === "string" ? data.path : "";
      const dir = data.dir && typeof data.dir === "object" ? data.dir : null;
      return viewHeaderHtml({
        className: "folder-header",
        path: path,
        eyebrow: viewHeaderEyebrowHtml(path),
        iconHtml: folderGlyphHtml(path),
        title: viewHeaderName(path),
        line: `<span class="folder-header-summary">${dir ? folderHeaderSummaryHtml(dir) : ""}</span>`,
      });
    }

    /**
     * A file's view header: eyebrow, the tree row's icon and its name, and its line.
     * @param {MetabrowserViewHeaderFile} data the file's envelope
     */
    function renderFileHeader(data) {
      const path = data.path || "";
      const name = viewHeaderName(path);
      // Keyed off the logical name, as a tree row's icon is.
      const icon = getFileIcon(
        getLogicalName({ name: name, compressed: data.compressed, compression: data.compression }),
      );
      return viewHeaderHtml({
        path: path,
        // Copy path at the eyebrow's end, so the title keeps the heading row's width.
        eyebrow:
          viewHeaderEyebrowHtml(path) +
          `<button class="icon-btn icon-btn-reveal file-header-copy" type="button" data-mb-copy="text" data-mb-copy-text="${esc(window.MetabrowserNavigationRoute.displayPath(path))}"${ownedControlAttr()} data-mb-copy-label="Copy path" data-tip-text="Copy path" aria-label="Copy path">` +
          (window.MetabrowserIcons?.copy || "") +
          "</button>",
        iconHtml: icon.svg,
        iconId: icon.id,
        iconClass: icon.cls,
        iconStyle: icon.style,
        title: name,
        line:
          renderBadges(data) +
          viewHeaderItemsHtml([
            sizeHtml(data.size, "file-header-size"),
            viewHeaderAgeHtml(data.mtime),
          ]),
      });
    }

    /**
     * A line's age, "11m ago": a skeleton while pending, nothing where there is no time.
     * @param {number | null | undefined} mtime epoch seconds
     */
    function viewHeaderAgeHtml(mtime) {
      if (mtime === undefined) {
        return "";
      }
      const age = formatAge(mtime, { style: "relative" });
      return age ? `<span class="view-header-age">${age}</span>` : "";
    }

    /**
     * Aggregate items of the folder header's line. Split out so the live refresher in
     * app.js can patch them in place when the inventory changes.
     * @param {MetabrowserViewHeaderFolderTotals} dirInfo the folder envelope's `dir`
     */
    function folderHeaderSummaryHtml(dirInfo) {
      // A still-finalizing directory reports null aggregates; sizeHtml,
      // countHtml, and formatAge(null) all render the tally-pending
      // skeleton the tree rows use, so the header paints with shape
      // instead of blanks until the live refresher patches it.
      // Omitted aggregates are not pending: a Git tree envelope has no dir.
      // Nor are a folder's the inventory leaves out: they will never arrive.
      if (dirInfo.not_indexed) {
        return "";
      }
      // The age is last, so its label changing width moves nothing.
      return viewHeaderItemsHtml([
        sizeHtml(dirInfo.total_size, "file-header-size"),
        countHtml(dirInfo.total_files, "folder-header-count"),
        viewHeaderAgeHtml(dirInfo.mtime),
      ]);
    }

    /**
     * A file's badges, from its kind (data-driven).
     * @param {MetabrowserViewHeaderFile} data the file's envelope
     */
    function renderBadges(data) {
      let badges = "";
      // Compression status — surfaced first so it's adjacent to the path.
      // Mirrors the .compression-badge overlay on the tree icon, with
      // text rather than a glyph since file-header badges are larger.
      if (data?.compressed) {
        const label = data.compression
          ? data.compression.charAt(0).toUpperCase() + data.compression.slice(1)
          : "Compressed";
        badges +=
          '<span class="file-header-badge badge-compressed" data-tip-text="On-disk file is ' +
          esc(label.toLowerCase()) +
          '-compressed">' +
          esc(label) +
          "</span>";
      }
      if (data.summary?.adapter && data.summary.adapter !== "unknown") {
        const adapterLabel = String(data.summary.adapter)
          .replace(/[-_]+/g, " ")
          .replace(/\b\w/g, (letter) => letter.toUpperCase());
        badges += `<span class="file-header-badge badge-adapter">${esc(adapterLabel)}</span>`;
      }
      // Status badge for JSONL kinds. It changes its label in place, Running to Live and Live
      // to Run ended, so it sits in a slot as wide as the widest label from first paint.
      if (data.type === "jsonl" && data.summary) {
        const statusSummary = data.summary;
        const statusBadge = statusSummary.is_done
          ? statusSummary.is_error
            ? '<span class="file-header-badge badge-failed">Failed</span>'
            : '<span class="file-header-badge badge-completed">Done</span>'
          : activeFiles.has(data.path)
            ? '<span class="file-header-badge badge-live">Live</span>'
            : '<span class="file-header-badge badge-running">Running</span>';
        badges += `<span class="file-header-badge-slot">${statusBadge}${RUN_STATUS_SIZERS}</span>`;
      }
      // Frontmatter parse error — surfaced as a red warning badge with the
      // YAML parser's message in the tooltip. /api/file populates this on
      // .md files where the leading --- ... --- block is present but
      // unparsable; absent frontmatter does NOT trigger this. The warning
      // hides a producer bug (e.g. tab characters, unmatched quotes); the
      // file still renders because classification falls back to generic
      // markdown, but the operator now sees that the frontmatter was
      // ignored rather than silently using an unparsable value.
      if (data.frontmatter_error) {
        badges +=
          '<span class="file-header-badge badge-frontmatter-error" data-tip-text="' +
          esc(data.frontmatter_error) +
          '">Frontmatter error</span>';
      }
      return badges;
    }

    return Object.freeze({
      folderHeaderSummaryHtml,
      renderBadges,
      renderFileHeader,
      renderFolderHeader,
      viewHeaderAgeHtml,
      viewHeaderEyebrowHtml,
      viewHeaderHtml,
      viewHeaderItemsHtml,
      viewHeaderName,
      viewHeaderUpHtml,
    });
  }

  window.MetabrowserViewHeader = Object.freeze({ create });
})();
