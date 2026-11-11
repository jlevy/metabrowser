// The PR-only rendered Markdown layer. Source stays hydrated by the diff's
// existing scheduler, so a refusal or a reader's Source selection has a patch ready.

const SNAPSHOT_ROUTE = "/api/plugin/github/pull-snapshot";
const SNAPSHOT_ORIGIN = "http://metabrowser.invalid";
const CONTEXT_BLOCKS = 2;
const MARKDOWN = /\.(?:md|markdown|mdown|mkd)$/i;

/** @typedef {Parameters<MetabrowserPublicSdk["loadKpressAssets"]>[0]} KpressAssetManifest */
/** @typedef {"rendered" | "source"} Mode */
/** @typedef {{kind: "context" | "removed" | "added", html: string}} Block */
/** @typedef {{
 *   section: HTMLElement, bar: HTMLElement, source: HTMLElement, rendered: HTMLElement,
 *   progress: HTMLElement, fallback: HTMLElement, control: HTMLElement,
 *   id: string, mode: Mode, pending: boolean, expanded: boolean,
 *   state: "idle" | "ready" | "unavailable"
 * }} FileView */

/**
 * Keep the feature extensible by admitting file kinds here and leaving source
 * comparisons, rendering and repository reads with their existing owners.
 * @param {Record<string, unknown>} change
 */
export function supportsMarkdownChange(change) {
  if (change.availability !== "ready" && change.availability !== "deferred") {
    return false;
  }
  return (
    [change.old, change.new].some(Boolean) &&
    [change.old, change.new].every((side) => {
      if (side == null) {
        return true;
      }
      const entry = /** @type {{entry_type?: unknown, path?: unknown}} */ (side);
      return (
        entry.entry_type === "file" && typeof entry.path === "string" && MARKDOWN.test(entry.path)
      );
    })
  );
}

/** @param {unknown} value @returns {value is {version: string, status: string, blocks: Block[], source_only: boolean, assets?: KpressAssetManifest}} */
function isProjection(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const answer =
    /** @type {{version?: unknown, status?: unknown, blocks?: unknown, source_only?: unknown}} */ (
      value
    );
  return (
    answer.version === "markdown-diff-v1" &&
    answer.status === "ready" &&
    typeof answer.source_only === "boolean" &&
    Array.isArray(answer.blocks) &&
    answer.blocks.every(
      (block) =>
        block !== null &&
        typeof block === "object" &&
        ["context", "removed", "added"].includes(block.kind) &&
        typeof block.html === "string",
    )
  );
}

/** @param {string} value @param {boolean} image */
export function isSnapshotTarget(value, image) {
  if (!value.startsWith(`${SNAPSHOT_ROUTE}?`)) {
    return false;
  }
  const url = new URL(value, SNAPSHOT_ORIGIN);
  const query = url.searchParams;
  return (
    url.origin === SNAPSHOT_ORIGIN &&
    url.pathname === SNAPSHOT_ROUTE &&
    /^\d{1,10}$/.test(query.get("number") ?? "") &&
    [query.get("left"), query.get("right")].every((oid) =>
      /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(oid ?? ""),
    ) &&
    /^[a-f0-9]{16}$/.test(query.get("store") ?? "") &&
    /^(?:base|head)$/.test(query.get("side") ?? "") &&
    /^g1-[\w-]+(?:\/g1-[\w-]+)*$/.test(query.get("path") ?? "") &&
    (image ? query.get("mode") === "image" : [null, "document"].includes(query.get("mode")))
  );
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
 * explicit snapshot addresses through it and discard other local targets
 * before the detached nodes can load any resource.
 * @param {string} html
 * @param {MetabrowserInertHtmlRuntime} inert
 * @param {HTMLTemplateElement} template
 * @param {Document} scratch
 */
function sanitizeBlock(html, inert, template, scratch) {
  template.innerHTML = html;
  /** @type {Map<string, string>} */
  const targets = new Map();
  for (const element of template.content.querySelectorAll("a[href], img[src]")) {
    const image = element.tagName === "IMG";
    const attribute = image ? "src" : "href";
    const value = element.getAttribute(attribute) ?? "";
    if (isSnapshotTarget(value, image)) {
      const marker = `mb-snapshot-target-${targets.size}`;
      targets.set(marker, value);
      element.setAttribute(attribute, marker);
    } else if (image || (!value.startsWith(`#${inert.ANCHOR_PREFIX}`) && !outsideLink(value))) {
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
 * Keep unchanged runs around an edit readable and fold their long interiors.
 * Native details can also reveal a heading when a fragment targets it.
 * @param {DocumentFragment} fragment
 * @param {Array<{kind: Block["kind"], row: HTMLElement}>} rows
 */
function appendContext(fragment, rows) {
  let index = 0;
  while (index < rows.length) {
    if (rows[index].kind !== "context") {
      fragment.append(rows[index++].row);
      continue;
    }
    const first = index;
    while (index < rows.length && rows[index].kind === "context") {
      index += 1;
    }
    const context = rows.slice(first, index).map(({ row }) => row);
    if (context.length <= 2 * CONTEXT_BLOCKS + 1) {
      fragment.append(...context);
      continue;
    }
    const hidden = context.slice(CONTEXT_BLOCKS, -CONTEXT_BLOCKS);
    const details = document.createElement("details");
    details.className = "diff-markdown-context";
    const summary = document.createElement("summary");
    summary.textContent = `${hidden.length} unchanged blocks`;
    details.append(summary, ...hidden);
    fragment.append(
      ...context.slice(0, CONTEXT_BLOCKS),
      details,
      ...context.slice(-CONTEXT_BLOCKS),
    );
  }
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
        /^\/kpress-static\/[\w./%-]+\.css$/.test(asset.public_url ?? ""),
    ),
  };
}

/**
 * One queue for a mounted comparison. A file that leaves the lookahead or
 * switches to Source detaches, and a replacement waits for teardown.
 * @param {{
 *   load: (fileId: string, signal: AbortSignal) => Promise<unknown>,
 *   controls: NonNullable<MetabrowserPublicSdk["filterControls"]>,
 *   ensureInert: () => Promise<MetabrowserInertHtmlRuntime | undefined>,
 *   loadStyles: (assets: KpressAssetManifest) => Promise<void>,
 *   mutate: (change: () => void) => void
 * }} deps
 */
export function createMarkdownViews(deps) {
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
  let disposed = false;
  let observed = false;
  /** @type {(() => void) | undefined} */
  let unbind;

  /** @param {FileView} file */
  function draw(file) {
    const rich = file.mode === "rendered" && file.state === "ready";
    file.source.hidden = rich;
    file.rendered.hidden = !file.expanded || !rich;
    file.fallback.hidden = !file.expanded || !file.fallback.textContent;
    drawProgress(file);
  }

  /** @param {FileView} file */
  function drawControl(file) {
    const restoreFocus = file.control.contains(document.activeElement);
    file.control.hidden = file.state === "unavailable";
    file.control.innerHTML = deps.controls.groupHtml({
      key: file.source.id,
      label: "Markdown diff format",
      layout: "joined",
      options: [
        { label: "Rendered", value: "rendered" },
        { label: "Source", value: "source" },
      ],
      select: "one",
      value: file.mode,
    });
    for (const chip of file.control.querySelectorAll("button[data-chip-value]")) {
      const button = /** @type {HTMLButtonElement} */ (chip);
      const mode = button.dataset.chipValue;
      button.setAttribute("aria-controls", mode === "rendered" ? file.rendered.id : file.source.id);
      button.disabled = mode === "rendered" && file.state === "unavailable";
      if (restoreFocus && !file.control.hidden && mode === file.mode) {
        button.focus();
      }
    }
    if (restoreFocus && file.control.hidden) {
      /** @type {HTMLElement | null} */ (file.bar.firstElementChild)?.focus();
    }
  }

  /** @param {FileView} file */
  function drawProgress(file) {
    file.progress.hidden = !file.pending || !file.expanded || file.mode === "source";
  }

  /** @param {FileView} file @param {boolean} pending */
  function progress(file, pending) {
    file.pending = pending;
    deps.mutate(() => drawProgress(file));
  }

  /** @param {FileView} file */
  function interested(file) {
    return nearby.has(file) && file.expanded && file.mode === "rendered" && file.state === "idle";
  }

  function pump() {
    if (disposed || !observed) {
      return;
    }
    if (active !== null) {
      if (!interested(active.file)) {
        active.controller.abort();
      }
      return;
    }
    const file = Array.from(nearby).find(interested);
    if (file === undefined) {
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    active = { file, controller };
    void load(file, signal);
  }

  /** @param {FileView} file @param {AbortSignal} signal */
  async function load(file, signal) {
    try {
      progress(file, true);
      const projection = await deps.load(file.id, signal);
      if (signal.aborted || disposed) {
        return;
      }
      if (!isProjection(projection)) {
        fallBack(file, true);
        return;
      }
      inertReady ??= deps.ensureInert();
      const inert = await inertReady;
      if (inert === undefined) {
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
      const scratch = document.implementation.createHTMLDocument("");
      const template = document.createElement("template");
      const rows = projection.blocks.map((block) => {
        const row = document.createElement("div");
        row.className = `diff-markdown-block diff-markdown-${block.kind}`;
        if (block.kind !== "context") {
          const label = document.createElement("span");
          label.className = "sr-only";
          label.textContent = block.kind === "added" ? "Added: " : "Removed: ";
          row.append(label);
        }
        row.append(sanitizeBlock(block.html, inert, template, scratch));
        return { kind: block.kind, row };
      });
      appendContext(content, rows);
      if (projection.source_only) {
        const note = document.createElement("p");
        note.className = "diff-availability";
        note.textContent = "Source shows additional changes.";
        content.prepend(note);
      }
      deps.mutate(() => {
        file.rendered.replaceChildren(content);
        file.state = "ready";
        draw(file);
      });
    } catch {
      if (!signal.aborted && !disposed) {
        fallBack(file, false);
      }
    } finally {
      if (!disposed) {
        progress(file, false);
      }
      active = null;
      pump();
    }
  }

  /** @param {FileView} file @param {boolean} unsupported */
  function fallBack(file, unsupported) {
    deps.mutate(() => {
      file.state = unsupported ? "unavailable" : "idle";
      file.mode = "source";
      file.fallback.textContent = unsupported
        ? "Rendered diff unavailable. Showing source."
        : "Could not render Markdown. Select Rendered to retry.";
      drawControl(file);
      draw(file);
    });
  }

  /** @param {FileView} file @param {Mode} mode */
  function select(file, mode) {
    if (disposed || file.mode === mode || (mode === "rendered" && file.state === "unavailable")) {
      return;
    }
    deps.mutate(() => {
      file.mode = mode;
      if (mode === "rendered") {
        file.fallback.textContent = "";
      }
      drawControl(file);
      draw(file);
    });
    pump();
  }

  return {
    /** @param {{section: HTMLElement, bar: HTMLElement, source: HTMLElement, id: string}} input */
    add({ section, bar, source, id }) {
      const control = document.createElement("div");
      control.className = "diff-markdown-control";
      const rendered = document.createElement("article");
      rendered.className = "kpress kpress-inert diff-markdown";
      rendered.id = `${source.id}-rendered`;
      const loading = document.createElement("div");
      loading.className = "diff-availability diff-markdown-progress";
      loading.setAttribute("role", "status");
      loading.hidden = true;
      const spinner = document.createElement("span");
      spinner.className = "index-progress-spinner";
      spinner.setAttribute("aria-hidden", "true");
      loading.append(spinner, document.createTextNode("Rendering Markdown…"));
      const fallback = document.createElement("p");
      fallback.className = "diff-availability diff-markdown-fallback";
      fallback.setAttribute("role", "status");
      /** @type {FileView} */
      const file = {
        section,
        bar,
        source,
        rendered,
        progress: loading,
        fallback,
        id,
        control,
        mode: "rendered",
        expanded: true,
        pending: false,
        state: "idle",
      };
      bar.firstElementChild?.after(control);
      bar.classList.add("diff-file-bar-markdown");
      source.before(loading, fallback, rendered);
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
    /** @param {HTMLElement} container @param {Element | null} root @param {number} ahead */
    observe(container, root, ahead) {
      observed = true;
      if (files.size === 0) {
        return;
      }
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
          for (const entry of entries) {
            const file = files.get(/** @type {HTMLElement} */ (entry.target));
            if (file !== undefined) {
              if (entry.isIntersecting) {
                nearby.add(file);
              } else {
                nearby.delete(file);
              }
            }
          }
          pump();
        },
        { root, rootMargin: `0px 0px ${ahead}px 0px` },
      );
      for (const section of files.keys()) {
        observer.observe(section);
      }
    },
    dispose() {
      disposed = true;
      observer?.disconnect();
      active?.controller.abort();
      if (active !== null) {
        active.file.progress.hidden = true;
      }
      unbind?.();
      unbind = undefined;
      files.clear();
      controls.clear();
      nearby.clear();
    },
  };
}
