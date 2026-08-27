// What a filter asks the server for, and what it decides about clustered rows.
//
// Two decisions that used to live inside a DOM walk in app.js. Neither needs a
// document: one turns a filter snapshot into request parameters, the other
// answers "which of these rows survive" given a description of them. Both are
// where the navigation panel's filtering bugs were, so both are testable
// headlessly here — see tests/dom/tree-filter-model-behavior.js — instead of
// only by looking at a browser.
//
// app.js keeps what genuinely needs the DOM: reading row state off elements and
// writing the verdicts back as classes.
//
// Where filtering happens at all is a separate question, answered in
// metabrowser/tree_filter.py: the /api/tree source is pruned server-side over
// the whole index, because whether a collapsed folder holds a match is not
// something a client that was never sent its contents can know. The cluster
// verdicts below apply only to the /api/recent source, whose folders are built
// out of the matching files themselves and are therefore complete.

(() => {
  /**
   * @typedef {object} FilterSnapshot
   * @property {string} recency
   * @property {string[] | null} types
   * @property {string} size
   * @property {boolean} showIgnored
   */

  /**
   * One row, as much of it as a verdict needs. `id` and `parentId` describe the
   * shape of the list; `matched` is the caller's own per-row predicate result.
   * @typedef {object} ClusterRow
   * @property {string} id
   * @property {string | null} parentId
   * @property {boolean} isDir
   * @property {boolean} matched
   */

  /**
   * The filter as `/api/tree` query parameters.
   *
   * Recency is deliberately absent: while a recency window is set the panel
   * reads from `/api/recent` instead, so in the tree source it is always "all".
   * The size floor travels as a byte count rather than a bucket name, so the
   * server needs no second copy of the bucket table.
   *
   * @param {FilterSnapshot | null} state
   * @param {Record<string, number>} sizeFloors bucket name -> minimum bytes
   * @returns {string[]}
   */
  function requestParams(state, sizeFloors) {
    /** @type {string[]} */
    const params = [];
    if (!state) {
      return params;
    }
    if (state.types && state.types.length > 0) {
      params.push(`types=${encodeURIComponent(state.types.join(","))}`);
    }
    const floor = sizeFloors?.[state.size];
    if (floor) {
      params.push(`min_size=${floor}`);
    }
    if (state.showIgnored === false) {
      params.push("include_ignored=0");
    }
    return params;
  }

  /**
   * Identity of a filter selection, for caching a fetched subtree against the
   * selection it was fetched under. Without it, narrowing the filter would
   * expand folders out of a cache filled while it was wider.
   *
   * @param {FilterSnapshot | null} state
   * @param {Record<string, number>} sizeFloors
   */
  function requestKey(state, sizeFloors) {
    return requestParams(state, sizeFloors).join("&");
  }

  /**
   * A `/api/tree` URL carrying the filter, an optional subtree path, and
   * whatever else the caller needs.
   *
   * @param {string} path
   * @param {FilterSnapshot | null} state
   * @param {Record<string, number>} sizeFloors
   * @param {string[]} [extraParams]
   */
  function treeUrl(path, state, sizeFloors, extraParams) {
    const params = requestParams(state, sizeFloors).concat(extraParams || []);
    if (path) {
      params.unshift(`path=${encodeURIComponent(path)}`);
    }
    return params.length > 0 ? `/api/tree?${params.join("&")}` : "/api/tree";
  }

  /**
   * Which rows a filter hides, in a list whose folders are complete.
   *
   * Two passes over *rows*, which must be in document order:
   *
   * 1. Backwards, so a folder is judged after its descendants and can ask
   *    whether any of them survived. A folder with no surviving child is
   *    hidden — sound here only because this source's folders hold every
   *    matching file they have. The tree source cannot ask this question,
   *    which is the whole reason its filtering moved to the server.
   * 2. Forwards, so a hidden folder is seen before its descendants and its
   *    verdict propagates down. Without it a matching row could stay visible
   *    inside a pruned subtree, floating under a parent that is gone.
   *
   * @param {ClusterRow[]} rows
   * @returns {Set<string>} ids to hide
   */
  function clusterHiddenIds(rows) {
    /** @type {Map<string, boolean>} */
    const keep = new Map();
    /** @type {Map<string, string[]>} */
    const childIds = new Map();
    for (const row of rows) {
      if (row.parentId !== null && row.parentId !== undefined) {
        const siblings = childIds.get(row.parentId);
        if (siblings) {
          siblings.push(row.id);
        } else {
          childIds.set(row.parentId, [row.id]);
        }
      }
    }
    for (let index = rows.length - 1; index >= 0; index -= 1) {
      const row = rows[index];
      let ok = row.matched;
      if (row.isDir && ok) {
        const kids = childIds.get(row.id) || [];
        ok = kids.length > 0 && kids.some((id) => keep.get(id) === true);
      }
      keep.set(row.id, ok);
    }
    /** @type {Set<string>} */
    const hidden = new Set();
    for (const row of rows) {
      const parentHidden =
        row.parentId !== null && row.parentId !== undefined && hidden.has(row.parentId);
      if (parentHidden || keep.get(row.id) !== true) {
        hidden.add(row.id);
      }
    }
    return hidden;
  }

  window.MetabrowserTreeFilterModel = Object.freeze({
    clusterHiddenIds,
    requestKey,
    requestParams,
    treeUrl,
  });
})();
