// Render an ordered page of typed nodes. The caller owns the resource identity and
// supplies the page reader so an embedded view can use the same rendering path.
import { createCopyButton } from "./copy-button.js";
import { showStructuredNotice, structuredFailure } from "./structured-page-reader.js";

/** @typedef {string | number} Segment */
/** @typedef {{kind: string, child_count: number, value?: unknown, children?: Child[]}} ProjectionNode */
/** @typedef {{segment: Segment, node: ProjectionNode}} Child */
/** @typedef {{status: string, diagnostic?: string, mtime_hash?: string, document_count?: number, record_table?: boolean, node?: ProjectionNode, children?: Child[], next_offset?: number | null, copy_text?: string}} Page */
/** @typedef {{document: number, path: Segment[], offset: number}} Position */
/** @typedef {(position: Position, signal: AbortSignal, depth: number) => Promise<Page>} ReadPage */
/** @typedef {(label: string, position: Position) => HTMLButtonElement} CreateRowCopy */

// The depth-three Universe preview fit within the row budget across the sampled records.
const PREVIEW_DEPTH = 3;
// Match the Tree preview's character budget. Work stops within that budget and uses
// only the projected children already present, preserving numeric spelling and order.
const PREVIEW_CHARS = 80;

/** @param {ProjectionNode} node */
function isContainer(node) {
  return node.kind === "object" || node.kind === "array";
}

/** @param {ProjectionNode} node */
function describe(node) {
  if (isContainer(node)) {
    return node.kind === "object" ? "{}" : "[]";
  }
  return node.kind === "string" ? JSON.stringify(node.value) : String(node.value);
}

/** @param {ProjectionNode} node */
function total(node) {
  const unit = node.kind === "object" ? "key" : "item";
  return `${node.child_count} ${unit}${node.child_count === 1 ? "" : "s"}`;
}

/** @param {string} value @param {number} budget */
function quotedPreview(value, budget) {
  let prefix = value.slice(0, budget);
  const complete = JSON.stringify(prefix);
  if (prefix.length === value.length && complete.length <= budget) {
    return { text: complete, complete: true };
  }
  if (budget < 3) {
    return { text: "…", complete: false };
  }
  while (JSON.stringify(`${prefix}…`).length > budget) {
    prefix = prefix.slice(0, -1);
  }
  return { text: JSON.stringify(`${prefix}…`), complete: false };
}

/** @param {ProjectionNode} node @param {number} budget
 * @returns {{text: string, complete: boolean}}
 */
function valuePreview(node, budget) {
  if (!isContainer(node)) {
    if (node.kind === "string") {
      return quotedPreview(String(node.value), budget);
    }
    const text = String(node.value);
    return text.length <= budget
      ? { text, complete: true }
      : { text: `${text.slice(0, Math.max(0, budget - 1))}…`, complete: false };
  }
  if (budget < 2 || (node.child_count && budget < 3)) {
    return { text: "…", complete: false };
  }
  const [open, close] = node.kind === "object" ? ["{", "}"] : ["[", "]"];
  const children = node.children ?? [];
  /** @type {string[]} */
  const parts = [];
  let remaining = budget - 2;
  let complete = true;
  for (const child of children) {
    const separator = parts.length ? 2 : 0;
    let key = "";
    if (node.kind === "object") {
      const preview = quotedPreview(String(child.segment), Math.max(0, remaining - separator - 3));
      if (!preview.complete) {
        break;
      }
      key = `${preview.text}: `;
    }
    const omission = parts.length + 1 < node.child_count ? 3 : 0;
    const available = remaining - separator - key.length - omission;
    if (available < 1) {
      break;
    }
    const preview = valuePreview(child.node, available);
    parts.push(`${key}${preview.text}`);
    remaining -= separator + key.length + preview.text.length;
    if (!preview.complete) {
      complete = false;
      break;
    }
  }
  if (parts.length < node.child_count) {
    // Leave room for the omission mark rather than making a partial page look whole.
    while (parts.length && remaining < 3) {
      remaining += (parts.pop()?.length ?? 0) + (parts.length ? 2 : 0);
    }
    parts.push("…");
    complete = false;
  }
  return { text: `${open}${parts.join(", ")}${close}`, complete };
}

/**
 * @param {HTMLElement} host
 * @param {ReadPage} readPage
 * @param {{
 *   mountRecords?: (container: HTMLElement, createRowCopy?: CreateRowCopy) => Promise<{dispose: () => void}>,
 *   openSource?: (position: Position) => void,
 *   onSelect?: (position: Position) => void,
 *   copyRow?: (position: Position, signal: AbortSignal) => Promise<string>,
 * }} [options]
 */
export function mountNodeTable(host, readPage, options = {}) {
  const doc = host.ownerDocument;
  const { copyRow } = options;
  /** @param {HTMLElement} target @param {string} message @param {Position} address */
  function showFailure(target, message, address) {
    const open = options.openSource;
    showStructuredNotice(target, message, open ? () => open(address) : undefined);
  }
  /** @type {Position} */
  let position = { document: 0, path: [], offset: 0 };
  /** @type {number[]} */
  const earlierPages = [];
  /** @type {AbortController | undefined} */
  let pending;
  /** @type {{dispose: () => void} | undefined} */
  let records;
  let disposed = false;
  let fitting = false;
  /** @type {Set<{opener: HTMLElement, preview: HTMLElement, count: HTMLElement}>} */
  const previews = new Set();

  function fitPreviews() {
    if (disposed || fitting) {
      return;
    }
    fitting = true;
    queueMicrotask(() => {
      fitting = false;
      if (disposed) {
        return;
      }
      // Test the complete preview without its count, then reveal counts in one batch.
      // One observer watches the table host, not each row; removed branches are pruned.
      for (const item of previews) {
        if (host.contains(item.opener)) {
          item.count.hidden = true;
        } else {
          previews.delete(item);
        }
      }
      const clipped = [...previews].filter(
        ({ preview }) => preview.clientWidth > 0 && preview.scrollWidth > preview.clientWidth,
      );
      for (const item of clipped) {
        item.count.hidden = false;
      }
    });
  }
  const observer = doc.defaultView?.ResizeObserver
    ? new doc.defaultView.ResizeObserver(fitPreviews)
    : undefined;
  observer?.observe(host);

  /** @param {string} title @param {() => void} action */
  function button(title, action) {
    const item = doc.createElement("button");
    item.className = "btn";
    item.type = "button";
    item.textContent = title;
    item.addEventListener("click", action);
    return item;
  }

  /** @param {HTMLTableRowElement} row @param {Position} address @param {AbortSignal} signal */
  function addCopy(row, address, signal) {
    if (!copyRow) {
      return;
    }
    const cell = doc.createElement("td");
    cell.className = "structured-row-action data-grid-row-action";
    const segment = address.path.at(-1);
    const subject = segment === undefined ? "value" : String(segment) || '""';
    cell.append(
      createCopyButton(doc, `Copy ${subject}`, (attempt) => copyRow(address, attempt), signal),
    );
    row.append(cell);
  }

  /**
   * @param {HTMLTableSectionElement} body
   * @param {Child[]} children
   * @param {Position} parent
   * @param {Node | null} before
   * @param {AbortSignal} signal
   */
  function drawChildren(body, children, parent, before, signal) {
    for (const { segment, node } of children) {
      const address = { document: parent.document, path: [...parent.path, segment], offset: 0 };
      const row = doc.createElement("tr");
      const key = doc.createElement("th");
      key.scope = "row";
      key.textContent = segment === "" ? '""' : String(segment);
      if (parent.path.length) {
        key.style.paddingInlineStart = `${parent.path.length}em`;
      }
      const value = doc.createElement("td");
      row.append(key, value);
      addCopy(row, address, signal);
      body.insertBefore(row, before);
      if (!isContainer(node) || !node.child_count) {
        value.textContent = describe(node);
        continue;
      }

      // A comment marks the end of this branch without adding a visible table row.
      const end = doc.createComment("");
      body.insertBefore(end, before);
      const initial = node.children ?? [];
      let visible = initial;
      let offset = 0;
      let next = initial.length < node.child_count ? initial.length : null;
      let expanded = initial.length > 0;
      let loading = false;
      let failure = "";
      const opener = button("", () => {
        options.onSelect?.(address);
        expanded = !expanded;
        if (expanded && !visible.length && !failure && !loading) {
          void load(0);
        } else {
          redraw();
        }
      });
      opener.className = "btn structured-branch-toggle disclosure-toggle";
      const chevron = doc.createElement("span");
      chevron.className = "structured-branch-chevron";
      chevron.setAttribute("aria-hidden", "true");
      chevron.innerHTML = doc.defaultView?.MetabrowserIcons?.toggle ?? "";
      const summary = valuePreview(node, PREVIEW_CHARS);
      const count = total(node);
      opener.setAttribute("aria-label", `${summary.text} (${count})`);
      opener.setAttribute("data-tip-text", `${summary.text} (${count})`);
      const preview = doc.createElement("span");
      preview.className = "structured-branch-preview";
      preview.textContent = summary.text;
      const countLabel = doc.createElement("span");
      countLabel.className = "structured-branch-count";
      countLabel.textContent = ` (${count})`;
      countLabel.hidden = summary.complete;
      if (summary.complete) {
        previews.add({ opener, preview, count: countLabel });
      }
      opener.replaceChildren(preview, countLabel, chevron);
      value.append(opener);
      redraw();

      function redraw() {
        fitPreviews();
        opener.setAttribute("aria-expanded", String(expanded));
        opener.classList.toggle("expanded", expanded);
        while (row.nextSibling && row.nextSibling !== end) {
          row.nextSibling.remove();
        }
        if (!expanded) {
          return;
        }
        drawChildren(body, visible, address, end, signal);
        if (!loading && !failure && !offset && next === null) {
          return;
        }
        const controls = doc.createElement("tr");
        const cell = doc.createElement("td");
        cell.colSpan = copyRow ? 3 : 2;
        if (failure) {
          showFailure(cell, failure, address);
        } else if (loading) {
          cell.setAttribute("role", "status");
          const delayed = doc.createElement("div");
          delayed.className = "mb-delayed-loading";
          const spinner = doc.createElement("div");
          spinner.className = "spinner spinner-sm";
          spinner.setAttribute("aria-hidden", "true");
          const label = doc.createElement("span");
          label.className = "sr-only";
          label.textContent = "Loading rows";
          delayed.append(spinner);
          cell.append(delayed, label);
        }
        if (!loading && offset) {
          cell.append(button("First page", () => void load(0, true)));
        }
        if (!loading && next !== null) {
          const target = next;
          cell.append(button(failure ? "Retry" : "More", () => void load(target, true)));
        }
        controls.append(cell);
        body.insertBefore(controls, end);
      }

      /** @param {number} target @param {boolean} [restoreFocus] */
      async function load(target, restoreFocus = false) {
        if (loading || signal.aborted) {
          return;
        }
        loading = true;
        failure = "";
        if (restoreFocus) {
          opener.focus();
        }
        redraw();
        try {
          const page = await readPage({ ...address, offset: target }, signal, 1);
          if (page.status !== "ready" || !page.node) {
            failure = structuredFailure(page, "Values");
            return;
          }
          visible = page.children ?? [];
          offset = target;
          next = page.next_offset ?? null;
        } catch (error) {
          failure = structuredFailure(error, "Values");
        } finally {
          loading = false;
          if (!signal.aborted && end.parentNode === body) {
            redraw();
          }
        }
      }
    }
  }

  async function show() {
    pending?.abort();
    records?.dispose();
    records = undefined;
    previews.clear();
    const request = new AbortController();
    pending = request;
    const address = position;
    const controls = doc.createElement("div");
    const content = doc.createElement("div");
    content.setAttribute("aria-busy", "true");
    host.replaceChildren(controls, content);
    options.onSelect?.(address);
    try {
      const page = await readPage(address, request.signal, PREVIEW_DEPTH);
      if (request.signal.aborted) {
        return;
      }
      if (page.record_table && options.mountRecords) {
        content.className = "table-view-mount";
        /** @type {CreateRowCopy | undefined} */
        const createRowCopy =
          page.status === "ready" && copyRow
            ? (label, selected) =>
                createCopyButton(doc, label, (signal) => copyRow(selected, signal), request.signal)
            : undefined;
        const mounted = await options.mountRecords(content, createRowCopy);
        if (request.signal.aborted) {
          mounted.dispose();
        } else {
          records = mounted;
        }
        return;
      }
      if (page.status !== "ready" || !page.node) {
        showFailure(content, structuredFailure(page, "Values"), address);
        return;
      }
      if ((page.document_count ?? 0) > 1) {
        const picker = doc.createElement("select");
        picker.setAttribute("aria-label", "Document");
        for (let index = 0; index < (page.document_count ?? 0); index++) {
          const choice = doc.createElement("option");
          choice.value = String(index);
          choice.textContent = `Document ${index + 1}`;
          picker.append(choice);
        }
        picker.value = String(address.document);
        picker.addEventListener("change", () => {
          earlierPages.length = 0;
          position = { document: Number(picker.value), path: [], offset: 0 };
          void show();
        });
        controls.append(picker);
      }
      const node = page.node;
      const container = isContainer(node);
      const table = doc.createElement("table");
      table.className = "data-grid structured-node-grid";
      const header = doc.createElement("tr");
      const hasChildren = container && node.child_count > 0;
      const headers = hasChildren
        ? [node.kind === "object" ? "Field" : "Index", "Value"]
        : ["Value"];
      for (const title of headers) {
        const cell = doc.createElement("th");
        cell.scope = "col";
        cell.textContent = title;
        header.append(cell);
      }
      if (copyRow) {
        const action = doc.createElement("th");
        action.className = "structured-row-action";
        action.scope = "col";
        action.setAttribute("aria-label", "Actions");
        header.append(action);
      }
      const head = doc.createElement("thead");
      head.append(header);
      const body = doc.createElement("tbody");
      if (hasChildren) {
        drawChildren(body, page.children ?? [], address, null, request.signal);
      } else {
        const row = doc.createElement("tr");
        const value = doc.createElement("td");
        value.textContent = container
          ? `Empty ${node.kind === "object" ? "mapping" : "sequence"}`
          : describe(node);
        row.append(value);
        addCopy(row, address, request.signal);
        body.append(row);
      }
      table.append(head, body);
      content.append(table);
      const previous = earlierPages.at(-1);
      if (previous !== undefined) {
        content.append(
          button("Previous page", () => {
            earlierPages.pop();
            position = { ...address, offset: previous };
            void show();
          }),
        );
      }
      const next = page.next_offset;
      if (next != null) {
        content.append(
          button("Next page", () => {
            earlierPages.push(address.offset);
            position = { ...address, offset: next };
            void show();
          }),
        );
      }
    } catch (error) {
      if (!request.signal.aborted) {
        showFailure(content, structuredFailure(error, "Values"), address);
      }
    } finally {
      content.removeAttribute("aria-busy");
    }
  }

  return {
    ready: show(),
    dispose() {
      disposed = true;
      observer?.disconnect();
      previews.clear();
      pending?.abort();
      records?.dispose();
    },
  };
}
