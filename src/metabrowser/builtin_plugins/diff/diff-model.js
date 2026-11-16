// Browser implementation of File Diff Format v1.
//
// The checked-in JSON Schema is the authority; this validator and the
// Python model are bound by the same conformance corpus, which the DOM
// behavior test runs case by case. Rules mirror the Pydantic side
// exactly, including extra-key rejection — a document one side accepts
// and the other refuses is the drift this file exists to prevent.

const CHANGE_KINDS = new Set([
  "added",
  "deleted",
  "modified",
  "renamed",
  "copied",
  "type_changed",
  "unmerged",
]);
const ENTRY_TYPES = new Set(["file", "symlink", "submodule"]);
const FILE_MODES = new Set(["100644", "100755", "120000", "160000"]);
const AVAILABILITY = new Set([
  "ready",
  "deferred",
  "binary",
  "too_large",
  "timed_out",
  "failed",
  "stale",
  "unsupported",
]);
const SNAPSHOT_KINDS = new Set(["commit", "tree", "index", "worktree", "patch", "empty"]);
const BASE_POLICIES = new Set(["direct", "merge_base", "first_parent"]);
const LINE_OPS = new Set(["context", "add", "del"]);
const CONTENT_KINDS = new Set(["git_object", "inline", "empty"]);
const ALGORITHMS = new Set(["myers", "histogram", "patience", "minimal"]);
const OID_RE = /^[0-9a-f]{40,64}$/;

class FormatError extends Error {}

/**
 * Throw on a failed rule; typed as an assertion so a passed
 * `Array.isArray(x)` narrows `x` for the caller.
 *
 * @param {boolean} condition
 * @param {string} message
 * @returns {asserts condition}
 */
function require(condition, message) {
  if (!condition) {
    throw new FormatError(message);
  }
}

/** @param {unknown} value @param {string} where @returns {Record<string, unknown>} */
function asObject(value, where) {
  require(typeof value === "object" &&
    value !== null &&
    !Array.isArray(value), `${where}: object required`);
  return /** @type {Record<string, unknown>} */ (value);
}

/** @param {Record<string, unknown>} obj @param {string[]} allowed @param {string} where */
function forbidExtras(obj, allowed, where) {
  for (const key of Object.keys(obj)) {
    require(allowed.includes(key), `${where}: unknown key ${key}`);
  }
}

/**
 * Optional fields treat an explicit null exactly as absence — the
 * interchange rule the schema states, and the Pydantic side's native
 * behavior, so the two implementations cannot drift on serializers
 * that emit nulls.
 *
 * @param {unknown} value
 * @returns {boolean}
 */
function absent(value) {
  return value === undefined || value === null;
}

/** @param {unknown} value @param {string} where */
function optionalString(value, where) {
  require(absent(value) || typeof value === "string", `${where}: string expected`);
}

/** @param {unknown} value @param {string} where @param {number} [min] */
function requireInt(value, where, min = 0) {
  require(typeof value === "number" &&
    Number.isInteger(value) &&
    value >= min, `${where}: integer >= ${min} required`);
}

/** @param {unknown} value @param {string} where */
function nullableCount(value, where) {
  require(value === null ||
    (typeof value === "number" &&
      Number.isInteger(value) &&
      value >= 0), `${where}: null or integer >= 0 required`);
}

/** @param {unknown} raw @param {string} where */
function validateContentRef(raw, where) {
  const ref = asObject(raw, where);
  forbidExtras(ref, ["kind", "oid", "inline_b64", "generation"], where);
  require(CONTENT_KINDS.has(String(ref.kind)), `${where}: bad kind`);
  optionalString(ref.oid, `${where}.oid`);
  if (!absent(ref.oid)) {
    require(OID_RE.test(String(ref.oid)), `${where}: bad oid`);
  }
  optionalString(ref.inline_b64, `${where}.inline_b64`);
  optionalString(ref.generation, `${where}.generation`);
  require(ref.kind !== "git_object" || !absent(ref.oid), `${where}: git_object requires oid`);
  require(ref.kind !== "inline" || !absent(ref.inline_b64), `${where}: inline requires inline_b64`);
}

/** @param {unknown} raw @param {string} where */
function validateSide(raw, where) {
  const side = asObject(raw, where);
  forbidExtras(side, ["path", "path_b64", "entry_type", "mode", "content", "size"], where);
  require(typeof side.path === "string", `${where}: path required`);
  optionalString(side.path_b64, `${where}.path_b64`);
  require(ENTRY_TYPES.has(String(side.entry_type)), `${where}: bad entry_type`);
  require(FILE_MODES.has(String(side.mode)), `${where}: bad mode`);
  validateContentRef(side.content, `${where}.content`);
  if (side.size !== undefined) {
    nullableCount(side.size, `${where}.size`);
  }
}

/** @param {unknown} raw @param {string} where */
function validateFileChange(raw, where) {
  const change = asObject(raw, where);
  forbidExtras(
    change,
    ["id", "kind", "old", "new", "similarity", "binary", "availability", "additions", "deletions"],
    where,
  );
  require(typeof change.id === "string" && change.id.length > 0, `${where}: id required`);
  const kind = String(change.kind);
  require(CHANGE_KINDS.has(kind), `${where}: bad kind`);
  require(typeof change.binary === "boolean", `${where}: binary must be boolean`);
  require(AVAILABILITY.has(String(change.availability)), `${where}: bad availability`);
  nullableCount(change.additions, `${where}.additions`);
  nullableCount(change.deletions, `${where}.deletions`);
  require("additions" in change &&
    "deletions" in change, `${where}: counts are required (nullable)`);
  if (change.binary === true) {
    require(change.additions === null &&
      change.deletions === null, `${where}: binary changes carry no line counts`);
  }
  const hasOld = !absent(change.old);
  const hasNew = !absent(change.new);
  if (hasOld) {
    validateSide(change.old, `${where}.old`);
  }
  if (hasNew) {
    validateSide(change.new, `${where}.new`);
  }
  if (!absent(change.similarity)) {
    requireInt(change.similarity, `${where}.similarity`);
    require(Number(change.similarity) <= 100, `${where}.similarity: <= 100`);
  }
  if (kind === "added") {
    require(!hasOld && hasNew, `${where}: added requires new and forbids old`);
  } else if (kind === "deleted") {
    require(hasOld && !hasNew, `${where}: deleted requires old and forbids new`);
  } else if (kind === "renamed" || kind === "copied") {
    require(hasOld &&
      hasNew &&
      !absent(change.similarity), `${where}: ${kind} requires both sides and similarity`);
  } else {
    require(hasOld && hasNew, `${where}: ${kind} requires both sides`);
  }
}

/** @param {unknown} raw @param {string} where */
function validateHunk(raw, where) {
  const hunk = asObject(raw, where);
  forbidExtras(
    hunk,
    ["old_start", "old_count", "new_start", "new_count", "heading", "lines"],
    where,
  );
  requireInt(hunk.old_start, `${where}.old_start`);
  requireInt(hunk.old_count, `${where}.old_count`);
  requireInt(hunk.new_start, `${where}.new_start`);
  requireInt(hunk.new_count, `${where}.new_count`);
  optionalString(hunk.heading, `${where}.heading`);
  const lines = hunk.lines;
  require(Array.isArray(lines), `${where}: lines required`);
  let sawOld = 0;
  let sawNew = 0;
  for (const [index, rawLine] of lines.entries()) {
    const line = asObject(rawLine, `${where}.lines[${index}]`);
    forbidExtras(line, ["op", "text", "text_b64", "no_newline"], `${where}.lines[${index}]`);
    require(LINE_OPS.has(String(line.op)), `${where}.lines[${index}]: bad op`);
    require(typeof line.text === "string", `${where}.lines[${index}]: text required`);
    optionalString(line.text_b64, `${where}.lines[${index}].text_b64`);
    require(line.no_newline === undefined ||
      typeof line.no_newline === "boolean", `${where}.lines[${index}]: no_newline must be boolean`);
    if (line.op !== "add") {
      sawOld += 1;
    }
    if (line.op !== "del") {
      sawNew += 1;
    }
  }
  require(sawOld === hunk.old_count &&
    sawNew === hunk.new_count, `${where}: hunk counts disagree with lines`);
}

/** @param {unknown} raw @param {string} where */
function validateFilePatch(raw, where) {
  const patch = asObject(raw, where);
  forbidExtras(patch, ["file_id", "hunks", "truncated"], where);
  require(typeof patch.file_id === "string" &&
    patch.file_id.length > 0, `${where}: file_id required`);
  require(typeof patch.truncated === "boolean", `${where}: truncated must be boolean`);
  const hunks = patch.hunks;
  require(Array.isArray(hunks), `${where}: hunks required`);
  for (const [index, hunk] of hunks.entries()) {
    validateHunk(hunk, `${where}.hunks[${index}]`);
  }
}

/** @param {unknown} raw @param {string} where */
function validateResolved(raw, where) {
  const resolved = asObject(raw, where);
  forbidExtras(
    resolved,
    ["comparison_id", "source", "kind", "base_policy", "left", "right", "options", "warnings"],
    where,
  );
  require(typeof resolved.comparison_id === "string" &&
    resolved.comparison_id.length > 0, `${where}: comparison_id required`);
  const source = asObject(resolved.source, `${where}.source`);
  forbidExtras(source, ["name", "version"], `${where}.source`);
  require(typeof source.name === "string" &&
    source.name.length > 0, `${where}: source.name required`);
  optionalString(source.version, `${where}.source.version`);
  require(resolved.kind === "content", `${where}: kind must be content`);
  require(BASE_POLICIES.has(String(resolved.base_policy)), `${where}: bad base_policy`);
  for (const sideName of ["left", "right"]) {
    const snap = asObject(resolved[sideName], `${where}.${sideName}`);
    forbidExtras(snap, ["kind", "id", "symbolic", "generation"], `${where}.${sideName}`);
    require(SNAPSHOT_KINDS.has(String(snap.kind)), `${where}.${sideName}: bad kind`);
    optionalString(snap.id, `${where}.${sideName}.id`);
    optionalString(snap.symbolic, `${where}.${sideName}.symbolic`);
    optionalString(snap.generation, `${where}.${sideName}.generation`);
  }
  const options = asObject(resolved.options, `${where}.options`);
  forbidExtras(
    options,
    ["context", "rename_detection", "rename_similarity", "algorithm"],
    `${where}.options`,
  );
  requireInt(options.context, `${where}.options.context`);
  require(typeof options.rename_detection === "boolean", `${where}.options.rename_detection`);
  if (options.rename_similarity !== undefined) {
    requireInt(options.rename_similarity, `${where}.options.rename_similarity`);
    require(Number(options.rename_similarity) <= 100, `${where}.options.rename_similarity`);
  }
  optionalString(options.algorithm, `${where}.options.algorithm`);
  if (!absent(options.algorithm)) {
    require(ALGORITHMS.has(String(options.algorithm)), `${where}.options.algorithm: bad value`);
  }
  const warnings = resolved.warnings;
  if (warnings !== undefined) {
    require(Array.isArray(warnings) &&
      warnings.every((entry) => typeof entry === "string"), `${where}.warnings: string list`);
  }
}

/**
 * A document's own keys, schema, and version.
 *
 * @param {unknown} raw
 * @returns {Record<string, unknown>}
 */
function checkEnvelope(raw) {
  const document = asObject(raw, "document");
  forbidExtras(
    document,
    ["schema", "schema_version", "resolved", "manifest", "patches"],
    "document",
  );
  require(document.schema === "file-diff-v1", "document: schema must be file-diff-v1");
  require(document.schema_version === 1, "document: unsupported schema_version");
  return document;
}

/**
 * A document's manifest: its changes, totals, and bound.
 *
 * @param {unknown} value
 * @returns {{manifest: Record<string, unknown>, ids: Set<string>}}
 */
function checkManifest(value) {
  const manifest = asObject(value, "manifest");
  forbidExtras(manifest, ["files", "totals", "truncated", "cursor"], "manifest");
  const files = manifest.files;
  require(Array.isArray(files), "manifest: files required");
  /** @type {Set<string>} */
  const ids = new Set();
  for (const [index, change] of files.entries()) {
    validateFileChange(change, `manifest.files[${index}]`);
    const id = String(asObject(change, "change").id);
    require(!ids.has(id), `manifest.files[${index}]: duplicate id ${id}`);
    ids.add(id);
  }
  const totals = asObject(manifest.totals, "manifest.totals");
  forbidExtras(totals, ["files", "additions", "deletions", "exact"], "manifest.totals");
  requireInt(totals.files, "manifest.totals.files");
  nullableCount(totals.additions, "manifest.totals.additions");
  nullableCount(totals.deletions, "manifest.totals.deletions");
  require("additions" in totals && "deletions" in totals, "manifest.totals: counts required");
  require(typeof totals.exact === "boolean", "manifest.totals.exact: boolean");
  require(typeof manifest.truncated === "boolean", "manifest.truncated: boolean");
  const cursor = manifest.cursor === undefined ? null : manifest.cursor;
  require(cursor === null || typeof cursor === "string", "manifest.cursor: null or string");
  require((cursor !== null) === Boolean(manifest.truncated), "manifest: cursor iff truncated");
  return { manifest, ids };
}

/**
 * Validate a ChangeSetDocument's envelope and manifest, and not what it resolved or its
 * patches, for a reader of the manifest alone: a page's Diff summary, which reads its list of
 * files and totals from a comparison whose patches the route bounds at 8 MiB. Validating the
 * whole of one, patches included, took a median of 16 ms on a 7.9 MB document in Node 24 at
 * a load average of 19 (A5 of review A on #470).
 *
 * @param {unknown} raw
 * @returns {{ok: true, manifest: Record<string, unknown>} | {ok: false, error: string}}
 */
export function validateManifest(raw) {
  try {
    const document = checkEnvelope(raw);
    return { ok: true, manifest: checkManifest(document.manifest).manifest };
  } catch (error) {
    if (error instanceof FormatError) {
      return { ok: false, error: error.message };
    }
    throw error;
  }
}

/**
 * Validate a full ChangeSetDocument.
 *
 * @param {unknown} raw
 * @returns {{ok: true, document: Record<string, unknown>} | {ok: false, error: string}}
 */
export function validateDocument(raw) {
  try {
    const document = checkEnvelope(raw);
    validateResolved(document.resolved, "resolved");
    const { ids } = checkManifest(document.manifest);
    const patches = asObject(document.patches, "patches");
    for (const [fileId, patch] of Object.entries(patches)) {
      validateFilePatch(patch, `patches.${fileId}`);
      require(/** @type {{file_id?: unknown}} */ (patch).file_id ===
        fileId, `patches.${fileId}: key and file_id disagree`);
      require(ids.has(fileId), `patches.${fileId}: no manifest entry`);
    }
    return { ok: true, document };
  } catch (error) {
    if (error instanceof FormatError) {
      return { ok: false, error: error.message };
    }
    throw error;
  }
}

const KIND_LETTERS = /** @type {Record<string, string>} */ ({
  added: "A",
  deleted: "D",
  modified: "M",
  renamed: "R",
  copied: "C",
  type_changed: "T",
  unmerged: "U",
});

/**
 * What a change set's tree calls each change kind: the statuses of the shell's changed-files
 * tree (static/changed-files-tree.js), which are GitHub's, so a diff's Diff summary and the
 * Pulls tab's tree of a pull request's files read alike.
 */
const SUMMARY_STATUSES = /** @type {Record<string, string>} */ ({
  added: "added",
  deleted: "removed",
  modified: "modified",
  renamed: "renamed",
  copied: "copied",
  type_changed: "changed",
  unmerged: "unmerged",
});

/**
 * One change as a row of its change set's tree: the path it has now, or had, for a file the
 * change deleted, which is the path the diff's jump finds it by; the path it came from, for a
 * rename or a copy; its status in the tree's words; and its line counts, null where the
 * change has none, as a binary file's. A path is whoever made the change's text, so what is
 * shown of it is *display*'s: the server's rule, `displayPath` of the shared changed-files
 * tree, which shows a control, format, or invisible character as U+FFFD.
 *
 * @param {Record<string, unknown>} change A validated change.
 * @param {(path: string) => string} display
 * @returns {MetabrowserChangedFileRow}
 */
export function changeSummaryRow(change, display) {
  const kind = String(change.kind);
  const oldSide = /** @type {{path?: unknown} | null | undefined} */ (change.old);
  const newSide = /** @type {{path?: unknown} | null | undefined} */ (change.new);
  const path = String((newSide ?? oldSide)?.path ?? "");
  const previous =
    (kind === "renamed" || kind === "copied") && oldSide ? String(oldSide.path ?? "") : null;
  /** @param {unknown} count */
  const lines = (count) => (typeof count === "number" ? count : null);
  return {
    path,
    previous_path: previous,
    status: SUMMARY_STATUSES[kind] ?? kind,
    additions: lines(change.additions),
    deletions: lines(change.deletions),
    display: display(path),
    previous_display: previous === null ? null : display(previous),
  };
}

/**
 * A change set's Diff summary, as a diff's toolbar draws it: its files as rows of the shared
 * changed-files tree, each shown by the server's display rule, and its header's words from
 * the manifest's totals and the statuses of the files it lists. Pure, so
 * tests/dom/diff-summary-session.js runs the call `renderDiffSummary` makes.
 *
 * *whole* is the whole change set's totals, for a list cut short at its bound where the page
 * knows more than the list, as a commit's page does from the commit's own stats (A3 of review
 * A on #470). The header then says those, with no breakdown, which would count only the
 * files listed, and how many files are listed (`listed`, null for a whole list).
 *
 * @param {Record<string, unknown>} totals The manifest's totals.
 * @param {ReadonlyArray<Record<string, unknown>>} files The manifest's validated changes.
 * @param {MetabrowserChangedFilesTree} model
 * @param {(count: number) => string} formatCount The shell's number format.
 * @param {{files: number, additions: number | null, deletions: number | null, exact: boolean} | null} [whole]
 */
export function diffSummaryOf(totals, files, model, formatCount, whole = null) {
  const rows = files.map((change) => changeSummaryRow(change, model.displayPath));
  if (whole !== null) {
    const said = model.describeChanges(whole, [], formatCount);
    const listed = formatCount(rows.length);
    return {
      rows,
      said: {
        ...said,
        text: `${said.text} (${listed} listed)`,
        label: `${said.label}; ${listed} listed`,
      },
      listed,
    };
  }
  /** @param {unknown} value */
  const lines = (value) => (typeof value === "number" ? value : null);
  const said = model.describeChanges(
    {
      files: Number(totals.files),
      additions: lines(totals.additions),
      deletions: lines(totals.deletions),
      exact: totals.exact === true,
    },
    rows.map((row) => row.status),
    formatCount,
  );
  return { rows, said, listed: null };
}

/**
 * A change set's totals as one line, for a diff whose shared changed-files tree did not
 * load: what main's toolbar said, "41 changed files +6,526 −555", in the shell's number
 * format, with "(estimated)" for totals that are not exact. `filesParts` is "41 changed
 * files" in a count summary's parts, its number bold where it is painted, as the Diff
 * summary's is. Pure.
 *
 * @param {Record<string, unknown>} totals
 * @param {(count: number) => string} formatCount
 */
export function plainTotals(totals, formatCount) {
  const files = Number(totals.files);
  /** @param {unknown} value */
  const count = (value) => (typeof value === "number" ? formatCount(value) : "?");
  return {
    /** @type {MetabrowserCountParts} */
    filesParts: [{ number: formatCount(files) }, ` changed ${files === 1 ? "file" : "files"}`],
    additions: `+${count(totals.additions)}`,
    deletions: `\u2212${count(totals.deletions)}`,
    estimated: totals.exact !== true,
  };
}

/**
 * The tree/list indicator for one change: letter, similarity, and the
 * transition notes GitHub-style badges are built from.
 *
 * The label shows each path through *display*: the server's display rule
 * (`displayPath` of the shared changed-files tree) where a page has it, so a control,
 * format, or invisible character a path's author put there shows as U+FFFD.
 *
 * @param {Record<string, unknown>} change
 * @param {(path: string) => string} [display]
 * @returns {{letter: string, label: string, notes: string[]}}
 */
export function fileChangeLabel(change, display = (path) => path) {
  const kind = String(change.kind);
  let letter = KIND_LETTERS[kind] || "?";
  if (change.similarity !== undefined && change.similarity !== null) {
    letter = `${letter}${change.similarity}`;
  }
  const oldSide = /** @type {{path?: string, mode?: string, entry_type?: string} | undefined} */ (
    change.old
  );
  const newSide = /** @type {{path?: string, mode?: string, entry_type?: string} | undefined} */ (
    change.new
  );
  const label =
    (kind === "renamed" || kind === "copied") && oldSide && newSide
      ? `${display(String(oldSide.path))} → ${display(String(newSide.path))}`
      : display(String((newSide || oldSide || { path: "?" }).path));
  const notes = [];
  if (oldSide && newSide && oldSide.mode !== newSide.mode) {
    notes.push(`${oldSide.mode}→${newSide.mode}`);
  }
  if (oldSide && newSide && oldSide.entry_type !== newSide.entry_type) {
    notes.push(`${oldSide.entry_type}→${newSide.entry_type}`);
  }
  if (change.binary) {
    notes.push("binary");
  }
  return { letter, label, notes };
}
