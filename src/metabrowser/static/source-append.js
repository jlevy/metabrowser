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

((global) => {
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
    // A text node, never innerHTML: the chunk is file content, and appending
    // it as markup would both corrupt the view and execute nothing good.
    code.appendChild(document.createTextNode(text));
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
    appendSourceText,
    commitChunkCache,
    nextCacheValue,
    nextChunkBytes,
    requestOwnsPreview,
    syncLoadMoreFooter,
    syncTruncationWarning,
  });
})(typeof window !== "undefined" ? window : globalThis);
