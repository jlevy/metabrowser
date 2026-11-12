// Incremental growth for the source view's chunked loading.
//
// Two decisions live here because both were wrong in the shell and both are
// worth testing directly. See docs/large-content-rendering.md for the
// measurements.
//
// 1. Appending, not re-rendering. Rebuilding the preview pane on every
//    Load more made each click cost the running total rather than the chunk
//    it loaded — 55 ms at 128 KB rising to 152 ms at 1.4 MB, quadratic across
//    a sequence of clicks.
//
// 2. Growing the request. A fixed small chunk is not conservative, it is just
//    slow to use: at 128 KiB a 4 MiB source file took 31 clicks. Doubling per
//    click reaches a large file in a handful of clicks while keeping the first
//    one small enough to open promptly.
//
// 3. Appending in text nodes of at most 64 KiB. One node per chunk was fine in
//    Chrome and five times slower in WebKit, which lays out a text node of
//    millions of characters slowly; the same text in nodes of the size WebKit's
//    HTML parser makes lays out there in about the time Chrome takes.

((global) => {
  /**
   * Longest text node an append creates, in UTF-16 code units, the unit a DOM
   * text node's length counts: 65,536, the size WebKit's HTML parser splits text
   * into (Chrome's does not split). Loading a 16 MiB source file in this view,
   * 2026-11-12, M1 Pro, medians of five back-to-back rounds: the 8 MiB click took
   * 8,063 ms in WebKit and 1,633 ms in Chrome as one node, and 1,794 ms against
   * 1,584 ms in nodes of this size. docs/large-content-rendering.md, "WebKit lays
   * out a long text node slowly", has the method and the other clicks.
   */
  const TEXT_NODE_MAX_LENGTH = 65_536;

  /** @type {Intl.Segmenter | null | undefined} */
  let graphemes;

  /** @param {number} code */
  const isHighSurrogate = (code) => code >= 0xd800 && code <= 0xdbff;
  /** @param {number} code */
  const isLowSurrogate = (code) => code >= 0xdc00 && code <= 0xdfff;

  /**
   * Where to cut a line longer than the bound, at or before `end`.
   *
   * Two ASCII characters always have a grapheme boundary between them, except CR
   * and LF, so a long line of ASCII, such as minified code, is cut at the bound
   * without a segmenter. Otherwise, where the engine has Intl.Segmenter, the cut
   * is the start of the grapheme cluster that holds `end`, so an accent, an emoji
   * sequence, or a flag stays whole. A boundary depends on the text before it, back
   * to the previous boundary: whether a regional indicator starts a flag depends
   * on how many precede it in its run. So the line is segmented from the last
   * position known to be a boundary, which makes the cut exact and never reaches
   * back past the piece: the piece's start, or, when an earlier cut fell inside a
   * cluster longer than the bound, that cluster's end.
   *
   * Without Intl.Segmenter, or inside one cluster longer than the bound, the cut is
   * the last code point boundary that keeps a surrogate pair and a CRLF whole: an
   * accent can then be cut from its letter. With a segmenter, the end of such a
   * cluster is found once, by segmenting forward from its start, so the cuts after
   * it are exact again.
   *
   * @param {string} text
   * @param {number} start Where the piece starts; the cut is after it.
   * @param {number} end The furthest cut the bound allows.
   * @param {{end: number}} inside The end of a cluster longer than the bound that an
   *   earlier cut fell inside, or 0; this sets it when a cut falls inside one.
   */
  function cutInsideLine(text, start, end, inside) {
    const before = text.charCodeAt(end - 1);
    const after = text.charCodeAt(end);
    if (before < 0x80 && after < 0x80 && !(before === 0x0d && after === 0x0a)) {
      return end;
    }
    if (graphemes === undefined) {
      graphemes =
        typeof Intl === "object" && typeof Intl.Segmenter === "function"
          ? new Intl.Segmenter(undefined, { granularity: "grapheme" })
          : null;
    }
    const from = Math.max(start, inside.end);
    if (graphemes && from <= end) {
      // Through the code point at `end`, which decides whether `end` is a boundary.
      const cluster = graphemes.segment(text.slice(from, end + 2)).containing(end - from);
      if (cluster && (cluster.index > 0 || from > start)) {
        return from + cluster.index;
      }
      // One cluster, starting at the piece's start, holds the whole window.
      inside.end = oversizedClusterEnd(graphemes, text, start, end);
    }
    let cut = end;
    if (cut - 1 > start && isLowSurrogate(after) && isHighSurrogate(before)) {
      cut -= 1;
    }
    if (cut - 1 > start && text.charCodeAt(cut - 1) === 0x0d && text.charCodeAt(cut) === 0x0a) {
      cut -= 1;
    }
    return cut;
  }

  /**
   * Where a grapheme cluster longer than the bound ends. It starts at `start`, a
   * boundary, and holds `end`. Each try segments twice as much text from its start
   * until the cluster ends inside the slice, so finding it is linear in its length.
   *
   * @param {Intl.Segmenter} segmenter
   * @param {string} text
   * @param {number} start
   * @param {number} end
   */
  function oversizedClusterEnd(segmenter, text, start, end) {
    for (let reach = 2 * (end - start); ; reach *= 2) {
      const stop = Math.min(text.length, start + reach);
      const cluster = segmenter.segment(text.slice(start, stop)).containing(end - start);
      const last = cluster ? start + cluster.index + cluster.segment.length : stop;
      // The code point after a boundary decides it, so it must be in the slice too.
      if (stop === text.length || last + 2 <= stop) {
        return last;
      }
    }
  }

  /**
   * Split text into pieces of at most `limit` code units that join back to it.
   * A piece ends at its last newline when it holds one, so ordinary source
   * code is split only between lines; a longer line is cut by cutInsideLine.
   *
   * @param {string} text
   * @param {number} [limit]
   * @returns {string[]}
   */
  function textPieces(text, limit = TEXT_NODE_MAX_LENGTH) {
    /** @type {string[]} */
    const pieces = [];
    const inside = { end: 0 };
    let start = 0;
    while (text.length - start > limit) {
      const end = start + limit;
      // Searched within the window only: lastIndexOf on the whole text would scan a
      // long line back to its start on every piece. A newline always ends its
      // cluster, so the position after one is a boundary.
      const newline = text.slice(start, end).lastIndexOf("\n");
      const cut = newline >= 0 ? start + newline + 1 : cutInsideLine(text, start, end, inside);
      pieces.push(text.slice(start, cut));
      start = cut;
    }
    if (start < text.length) {
      pieces.push(start === 0 ? text : text.slice(start));
    }
    return pieces;
  }

  /**
   * Bytes the next Load more should request.
   *
   * @param {number} current Bytes the last request asked for.
   * @param {number} cap Largest single request allowed.
   * @returns {number}
   */
  function nextChunkBytes(current, cap) {
    const previous = Number(current) > 0 ? Number(current) : 1;
    const ceiling = Number(cap) > 0 ? Number(cap) : previous;
    return Math.min(previous * 2, ceiling);
  }

  /**
   * Whether one chunk request still owns the exact preview and cache value it
   * started from. Path equality alone cannot distinguish leave-and-return ABA
   * navigation, and claim equality alone cannot detect a background cache
   * replacement.
   *
   * @param {{
   *   cached: Record<string, any>,
   *   cachedForPath: Record<string, any> | undefined,
   *   claim: number | null,
   *   currentPath: string | null,
   *   isClaimCurrent: (claim: number) => boolean,
   *   path: string,
   * }} options
   */
  function requestOwnsPreview(options) {
    return (
      options.currentPath === options.path &&
      options.claim !== null &&
      options.isClaimCurrent(options.claim) &&
      options.cachedForPath === options.cached
    );
  }

  /**
   * Construct the next immutable cache value without advancing the live
   * cursor. A fallback render can therefore fail without losing the Load more
   * control or making retry skip bytes.
   *
   * @param {Record<string, any>} cached
   * @param {Record<string, any>} chunk
   */
  function nextCacheValue(cached, chunk) {
    return {
      ...cached,
      content: (cached.content || "") + (chunk.content || ""),
      content_bytes: (cached.content_bytes || 0) + (chunk.content_bytes || 0),
      bytes_read: chunk.bytes_read || cached.bytes_read,
      content_truncated: !!chunk.content_truncated,
      highlight_disabled: !!chunk.highlight_disabled,
    };
  }

  /**
   * Advance cache content and growth cursor as one owned transaction.
   *
   * @param {{
   *   cached: Record<string, any>,
   *   cachedForPath: Record<string, any> | undefined,
   *   claim: number | null,
   *   commit: (nextCached: Record<string, any>) => void,
   *   currentPath: string | null,
   *   isClaimCurrent: (claim: number) => boolean,
   *   nextCached: Record<string, any>,
   *   path: string,
   *   requested: number,
   *   requestCap: number,
   * }} options
   * @returns {number | null} The next request size, or null when ownership was lost.
   */
  function commitChunkCache(options) {
    if (!requestOwnsPreview(options)) {
      return null;
    }
    options.commit(options.nextCached);
    return nextChunkBytes(options.requested, options.requestCap);
  }

  /**
   * Append text to a mounted source view without rebuilding it.
   *
   * Returns false when the view is not in the expected shape, so the caller
   * falls back to a full render rather than silently dropping content. A
   * highlighted block is one such shape: it carries markup a raw text append
   * would not survive.
   *
   * @param {ParentNode | null} root
   * @param {string} text
   * @returns {boolean}
   */
  function appendSourceText(root, text) {
    if (!text) {
      return true;
    }
    if (!root) {
      return false;
    }
    const host = root.querySelector(".metabrowser-source-host");
    const code = host ? host.querySelector("pre.code-block > code") : null;
    if (!code) {
      return false;
    }
    if (code.classList?.contains("hljs")) {
      return false;
    }
    // Text nodes, never innerHTML: the chunk is file content, and appending
    // it as markup would both corrupt the view and execute nothing good. They
    // go in as one fragment, so the tree changes once.
    const fragment = document.createDocumentFragment();
    for (const piece of textPieces(text)) {
      fragment.appendChild(document.createTextNode(piece));
    }
    code.appendChild(fragment);
    return true;
  }

  /**
   * Bring the partial-content banner in line with what is now loaded.
   *
   * Appending skips the plugin's render, so the banner it emitted keeps its
   * original byte counts and survives past the last chunk unless it is synced
   * here. Reporting "showing 2.0 MB of 4.0 MB" over a fully loaded file is a
   * worse failure than the cost the append avoids.
   *
   * @param {ParentNode | null} root
   * @param {string} markup Fresh banner markup, or "" when nothing remains.
   * @returns {boolean} Whether the banner now matches the loaded state.
   */
  function syncTruncationWarning(root, markup) {
    if (!root) {
      return false;
    }
    const existing = root.querySelector(".metabrowser-source-truncation-warning");
    if (!markup) {
      if (existing) {
        existing.remove();
      }
      return true;
    }
    if (existing) {
      existing.outerHTML = markup;
      return true;
    }
    const host = root.querySelector(".metabrowser-source-host");
    if (!host) {
      return false;
    }
    host.insertAdjacentHTML("afterbegin", markup);
    return true;
  }

  /**
   * Bring the trailing Load more control in line with what is now loaded.
   *
   * Same reason as the banner above, and the same failure if skipped — except
   * the footer is worse to leave stale, because it is the control the reader
   * just used. Removing it is how the view says "that was the last chunk".
   *
   * @param {ParentNode | null} root
   * @param {string} markup Fresh control markup, or "" when nothing remains.
   * @returns {boolean} Whether the footer now matches the loaded state.
   */
  function syncLoadMoreFooter(root, markup) {
    if (!root) {
      return false;
    }
    const existing = root.querySelector(".metabrowser-source-more-footer");
    if (!markup) {
      if (existing) {
        existing.remove();
      }
      return true;
    }
    if (existing) {
      existing.outerHTML = markup;
      return true;
    }
    const host = root.querySelector(".metabrowser-source-host");
    if (!host) {
      return false;
    }
    host.insertAdjacentHTML("beforeend", markup);
    return true;
  }

  /** @type {Record<string, unknown>} */ (global).MetabrowserSourceAppend = Object.freeze({
    TEXT_NODE_MAX_LENGTH,
    appendSourceText,
    commitChunkCache,
    nextCacheValue,
    nextChunkBytes,
    requestOwnsPreview,
    syncLoadMoreFooter,
    syncTruncationWarning,
    textPieces,
  });
})(typeof window !== "undefined" ? window : globalThis);
