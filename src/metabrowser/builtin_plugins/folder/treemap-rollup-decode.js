// Decode a compact /api/rollup body into the tree the treemap layout reads.
//
// The Treemap view asks for `encoding=compact` (treemap-map.js,
// treemapFullRollupQuery): every expanded folder's `children` holds only its
// folder children, and its file children arrive as positional entries in a
// `files` array, `[name, size, mtime, ext, gitignored]`, so a body at the full
// node budget does not repeat five keys and a path per file. This module puts
// them back as the file nodes an ordinary body carries, so the layout, the
// tooltip, and activation read one shape whichever encoding answered.
//
// The layout orders a folder's children by value, so the decoded files go
// after its folders in the order they arrived.

/** A compact file entry: `[name, size, mtime | null, ext, gitignored 0 | 1]`. */
/** @typedef {[string, number, number | null, string, number]} CompactFileEntry */

/**
 * Raised when a compact body does not hold the shape the route documents; the
 * caller reports it as a failed rollup rather than drawing part of a tree.
 */
export class CompactRollupError extends Error {
  /** @param {string} message */
  constructor(message) {
    super(message);
    this.name = "CompactRollupError";
  }
}

/**
 * The file node an ordinary rollup body carries for one compact entry.
 * @param {string} folderPath  the folder's root-relative path, "" at the root
 * @param {unknown} entry
 * @returns {Record<string, any>}
 */
function decodeFileEntry(folderPath, entry) {
  if (!Array.isArray(entry) || entry.length !== 5) {
    throw new CompactRollupError(`a compact file entry in "${folderPath}" is not five fields`);
  }
  const [name, size, mtime, ext, gitignored] = entry;
  if (
    typeof name !== "string" ||
    name === "" ||
    typeof size !== "number" ||
    !(mtime === null || typeof mtime === "number") ||
    typeof ext !== "string" ||
    (gitignored !== 0 && gitignored !== 1)
  ) {
    throw new CompactRollupError(
      `a compact file entry in "${folderPath}" has a field of the wrong type`,
    );
  }
  /** @type {Record<string, any>} */
  const node = {
    name,
    path: folderPath ? `${folderPath}/${name}` : name,
    type: "file",
    size,
  };
  // A body asked for without mtimes carries null, and an ordinary one omits the key.
  if (mtime !== null) {
    node.mtime = mtime;
  }
  node.ext = ext;
  node.gitignored = gitignored === 1;
  return node;
}

/**
 * The folder node with its compact files decoded into its children, and the
 * same for every folder under it. Iterative, so a deep tree cannot exhaust the
 * stack; each node is visited once.
 * @param {Record<string, any>} root
 * @returns {Record<string, any>}
 */
function decodeNode(root) {
  /** @type {Record<string, any>} */
  const top = { ...root };
  /** @type {Array<Record<string, any>>} */
  const stack = [top];
  while (stack.length > 0) {
    const node = /** @type {Record<string, any>} */ (stack.pop());
    if (node.type !== "dir") {
      continue;
    }
    const folders = Array.isArray(node.children) ? node.children : [];
    /** @type {Array<Record<string, any>>} */
    const children = [];
    for (const child of folders) {
      if (!child || typeof child !== "object") {
        throw new CompactRollupError(`a child of "${node.path}" is not a node`);
      }
      const copy = { ...child };
      children.push(copy);
      stack.push(copy);
    }
    if (node.files !== undefined) {
      if (!Array.isArray(node.files)) {
        throw new CompactRollupError(`the files of "${node.path}" are not a list`);
      }
      const folderPath = typeof node.path === "string" ? node.path : "";
      for (const entry of node.files) {
        children.push(decodeFileEntry(folderPath, entry));
      }
      delete node.files;
    }
    // An unexpanded folder keeps `children: null`, which says the budget did not reach
    // it, and an expanded one its folders and files.
    if (Array.isArray(node.children) || children.length > 0) {
      node.children = children;
    }
  }
  return top;
}

/**
 * A rollup envelope in the ordinary encoding. A compact one is decoded and
 * loses its `encoding` key; any other comes back as it is.
 * @param {Record<string, any>} envelope
 * @returns {Record<string, any>}
 */
export function decodeRollupEnvelope(envelope) {
  if (envelope?.encoding !== "compact") {
    return envelope;
  }
  const { encoding: _encoding, ...rest } = envelope;
  if (rest.node && typeof rest.node === "object") {
    rest.node = decodeNode(rest.node);
  }
  return rest;
}
