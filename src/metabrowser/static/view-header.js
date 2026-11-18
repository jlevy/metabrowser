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
      pathBaseName,
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
     * A view header's eyebrow address: the served root dimmed, the root slash, and a crumb
     * per folder above the item, whose name is the title; at the root, the directory that
     * holds it, dimmed. A crumb's tip is its name, shown only while it is cut short
     * (`tipAddsInformation` in app.js).
     * @param {string} path served-root-relative path; "" is the root itself
     */
    function headerEyebrowAddressHtml(path) {
      const root = servedRoot();
      const segments = path ? path.split("/") : [];
      // <bdi> isolates the path from .file-header-root's start-truncation direction.
      /** @param {string} text */
      const dimmed = (text) =>
        text ? `<span class="file-header-root"><bdi>${esc(text)}</bdi></span>` : "";
      if (segments.length === 0) {
        return dimmed(servedRootParent(root)) + mirrorHeading("note");
      }
      const rootCrumb = `<button type="button" class="folder-crumb folder-crumb-root" data-nav-dir=""${ownedControlAttr()} data-tip-text="Served root">/</button>`;
      const crumbs = [];
      let walked = "";
      for (let i = 0; i < segments.length - 1; i++) {
        walked = walked ? `${walked}/${segments[i]}` : segments[i];
        const name = esc(window.MetabrowserNavigationRoute.displayPath(segments[i]));
        crumbs.push(
          `<button type="button" class="folder-crumb" data-nav-dir="${esc(walked)}"${ownedControlAttr()} data-tip-text="${name}">${name}</button>`,
        );
      }
      return (
        dimmed(root) +
        rootCrumb +
        crumbs.join('<span class="folder-crumb-sep">/</span>') +
        mirrorHeading("note")
      );
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

    /** A view header's title: the item's name, or the served root's. @param {string} path */
    function viewHeaderName(path) {
      if (path) {
        const segments = path.split("/");
        return window.MetabrowserNavigationRoute.displayPath(segments[segments.length - 1]);
      }
      const root = servedRoot();
      return pathBaseName(root) || root || "/";
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
      return `<button type="button" class="btn parent-nav-btn parent-nav-btn-icon-only folder-up" ${attrs}><span class="parent-nav-arrow" aria-hidden="true">↑</span></button>`;
    }

    /**
     * A metadata line's items, each after a muted dot but the first and one box with it, so
     * a narrow line drops both whole (`.view-header-line`); an empty item is left out.
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
     * one leaves out, the heading row (icon and title), the header's corner, its controls,
     * and the metadata line. The corner is placed in the header's upper right whatever
     * the rows hold, and follows the heading row in the reading order.
     * @param {MetabrowserViewHeaderParts} parts
     */
    function viewHeaderHtml(parts) {
      return (
        `<div class="file-header view-header${parts.className ? ` ${parts.className}` : ""}" data-path="${esc(parts.path)}" data-kbd-badge-anchor>` +
        `<div class="view-header-eyebrow">${parts.eyebrow}</div>` +
        '<div class="view-header-heading">' +
        `<span class="view-header-icon file-identity-icon${parts.iconClass ? ` ${parts.iconClass}` : ""}"${parts.iconStyle ? ` style="${esc(parts.iconStyle)}"` : ""} aria-hidden="true">${parts.iconHtml}</span>` +
        `<h1 class="view-header-title page-heading" data-tip-text="${esc(parts.title)}">${esc(parts.title)}</h1>` +
        "</div>" +
        `<span class="view-header-end">${parts.end}</span>` +
        `<div class="view-header-line page-header-line">${parts.line}</div>` +
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
        iconHtml: window.MetabrowserIcons?.folder || "",
        title: viewHeaderName(path),
        end: "",
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
        iconClass: icon.cls,
        iconStyle: icon.style,
        title: name,
        end: "",
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
      const kind = data.kind;
      if (kind === "agent-log" && data.summary) {
        const summary = data.summary;
        if (summary.adapter === "claude") {
          badges += '<span class="file-header-badge badge-claude">Claude</span>';
        } else if (summary.adapter === "gemini") {
          badges += '<span class="file-header-badge badge-gemini">Gemini</span>';
        } else if (summary.adapter === "pi") {
          badges += '<span class="file-header-badge badge-pi">Pi</span>';
        }
      } else if (data.summary?.adapter && data.summary.adapter !== "unknown") {
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
