// Spike: custom dependency-free unified diff renderer over the FilePatch schema.
// Table-per-line DOM, textContent only, load-more gating, progressive changeset mount.

/**
 * @typedef {{type: "context" | "add" | "del", lines: string[], noNewline?: boolean}} Group
 * @typedef {{oldStart: number, oldLines: number, newStart: number, newLines: number,
 *   section: string, groups: Group[]}} Hunk
 * @typedef {{path: string, status: string, binary: boolean, additions: number | null,
 *   deletions: number | null, hunks: Hunk[], truncated: boolean}} FilePatch
 */

/**
 * Render one FilePatch as a unified diff table. Returns rendered row count.
 *
 * @param {HTMLElement} container
 * @param {FilePatch} patch
 * @param {{maxRows?: number}} [opts]
 */
export function renderFilePatch(container, patch, opts = {}) {
  const maxRows = opts.maxRows ?? 4000;
  const table = document.createElement("table");
  table.className = "dv-table";
  const tbody = document.createElement("tbody");
  let rows = 0;
  let gated = false;

  outer: for (const hunk of patch.hunks) {
    tbody.append(hunkRow(hunk));
    rows += 1;
    let oldNo = hunk.oldStart;
    let newNo = hunk.newStart;
    for (const group of hunk.groups) {
      for (const line of group.lines) {
        if (rows >= maxRows) {
          gated = true;
          break outer;
        }
        if (group.type === "context") {
          tbody.append(lineRow("dv-ctx", oldNo, newNo, " ", line));
          oldNo += 1;
          newNo += 1;
        } else if (group.type === "add") {
          tbody.append(lineRow("dv-add", null, newNo, "+", line));
          newNo += 1;
        } else {
          tbody.append(lineRow("dv-del", oldNo, null, "-", line));
          oldNo += 1;
        }
        rows += 1;
      }
    }
  }
  if (gated) {
    const total = patch.hunks.reduce(
      (n, h) => n + h.groups.reduce((m, g) => m + g.lines.length, 0),
      0,
    );
    tbody.append(gateRow(total - rows));
  }
  table.append(tbody);
  container.append(table);
  return rows;
}

/**
 * Render a changeset: eager sections first, the rest lazily via IntersectionObserver.
 *
 * @param {HTMLElement} container
 * @param {FilePatch[]} files
 * @param {{eager?: number, lineHeight?: number, maxRows?: number}} [opts]
 */
export function renderChangeset(container, files, opts = {}) {
  const eager = opts.eager ?? 8;
  const lineHeight = opts.lineHeight ?? 20;
  /** @type {Map<Element, FilePatch>} */
  const pending = new Map();
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const patch = pending.get(entry.target);
        if (!patch) continue;
        pending.delete(entry.target);
        observer.unobserve(entry.target);
        const body = /** @type {HTMLElement} */ (entry.target);
        body.classList.remove("dv-placeholder");
        body.style.minHeight = "";
        renderFilePatch(body, patch, opts);
      }
    },
    { rootMargin: "600px 0px" },
  );

  files.forEach((patch, index) => {
    const section = document.createElement("section");
    section.className = "dv-file";
    const header = document.createElement("div");
    header.className = "dv-file-header";
    header.append(
      textSpan("", patch.path + "  "),
      textSpan("dv-adds", `+${patch.additions ?? "?"} `),
      textSpan("dv-dels", `−${patch.deletions ?? "?"}`),
    );
    const body = document.createElement("div");
    section.append(header, body);
    container.append(section);
    if (index < eager) {
      renderFilePatch(body, patch, opts);
    } else {
      const rows = patch.hunks.reduce(
        (n, h) => n + 1 + h.groups.reduce((m, g) => m + g.lines.length, 0),
        0,
      );
      body.className = "dv-placeholder";
      body.style.minHeight = `${rows * lineHeight}px`;
      pending.set(body, patch);
      observer.observe(body);
    }
  });
  return observer;
}

/** @param {Hunk} hunk */
function hunkRow(hunk) {
  const tr = document.createElement("tr");
  tr.className = "dv-hunk";
  const td = document.createElement("td");
  td.colSpan = 4;
  td.textContent = `@@ -${hunk.oldStart},${hunk.oldLines} +${hunk.newStart},${hunk.newLines} @@ ${hunk.section}`;
  tr.append(td);
  return tr;
}

/**
 * @param {string} cls
 * @param {number | null} oldNo
 * @param {number | null} newNo
 * @param {string} sign
 * @param {string} line
 */
function lineRow(cls, oldNo, newNo, sign, line) {
  const tr = document.createElement("tr");
  tr.className = cls;
  const a = document.createElement("td");
  a.className = "dv-num";
  a.textContent = oldNo === null ? "" : String(oldNo);
  const b = document.createElement("td");
  b.className = "dv-num";
  b.textContent = newNo === null ? "" : String(newNo);
  const s = document.createElement("td");
  s.className = "dv-sign";
  s.textContent = sign;
  const code = document.createElement("td");
  code.className = "dv-code";
  code.textContent = line;
  tr.append(a, b, s, code);
  return tr;
}

/** @param {number} remaining */
function gateRow(remaining) {
  const tr = document.createElement("tr");
  tr.className = "dv-gate";
  const td = document.createElement("td");
  td.colSpan = 4;
  td.textContent = `Show ${remaining} more lines`;
  tr.append(td);
  return tr;
}

/**
 * @param {string} cls
 * @param {string} text
 */
function textSpan(cls, text) {
  const span = document.createElement("span");
  if (cls) span.className = cls;
  span.textContent = text;
  return span;
}
