// Bounded client state for the Git history panel.
//
// The server owns the unbounded history walk. This module owns only the
// browser working set: a fixed-size decoded-page cache and a fixed-height
// viewport model whose physical scroll segment never approaches the browser's
// element-height clamp. It deliberately has no DOM or network dependency, so
// the structural bounds can be tested without timing-sensitive browser work.

(() => {
  /** @param {number} value @param {number} minimum @param {number} maximum */
  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  /**
   * @param {unknown} value
   * @param {string} name
   * @param {{minimum?: number, allowZero?: boolean}} [options]
   * @returns {number}
   */
  function integer(value, name, options = {}) {
    const minimum = options.minimum ?? (options.allowZero ? 0 : 1);
    if (!Number.isSafeInteger(value) || Number(value) < minimum) {
      throw new RangeError(`${name} must be a safe integer >= ${minimum}`);
    }
    return Number(value);
  }

  /**
   * @param {{maxPages: number, onEvict?: (page: MetabrowserGitHistoryPage) => void}} options
   * @returns {MetabrowserGitHistoryPageCache}
   */
  function createPageCache(options) {
    const maxPages = integer(options.maxPages, "maxPages");
    /** @type {Map<number, MetabrowserGitHistoryPage>} */
    const pages = new Map();
    let disposed = false;

    /** @param {MetabrowserGitHistoryPage} page */
    function disposePage(page) {
      try {
        page.dispose?.();
      } finally {
        options.onEvict?.(page);
      }
    }

    function assertLive() {
      if (disposed) {
        throw new Error("Git history page cache is disposed");
      }
    }

    /** @param {number} pageNumber */
    function get(pageNumber) {
      assertLive();
      const key = integer(pageNumber, "page", { allowZero: true });
      const page = pages.get(key);
      if (!page) {
        return null;
      }
      pages.delete(key);
      pages.set(key, page);
      return page;
    }

    /** @param {number} pageNumber */
    function peek(pageNumber) {
      assertLive();
      const key = integer(pageNumber, "page", { allowZero: true });
      return pages.get(key) ?? null;
    }

    /** @param {MetabrowserGitHistoryPage} page */
    function put(page) {
      assertLive();
      const key = integer(page.page, "page", { allowZero: true });
      const existing = pages.get(key);
      if (existing && existing !== page) {
        disposePage(existing);
      }
      pages.delete(key);
      pages.set(key, page);
      while (pages.size > maxPages) {
        const oldest = pages.entries().next().value;
        if (!oldest) {
          break;
        }
        pages.delete(oldest[0]);
        disposePage(oldest[1]);
      }
      return page;
    }

    /** @param {number} pageNumber */
    function remove(pageNumber) {
      assertLive();
      const key = integer(pageNumber, "page", { allowZero: true });
      const page = pages.get(key);
      if (!page) {
        return false;
      }
      pages.delete(key);
      disposePage(page);
      return true;
    }

    function clear() {
      assertLive();
      const ownedPages = Array.from(pages.values());
      pages.clear();
      let firstError = null;
      for (const page of ownedPages) {
        try {
          disposePage(page);
        } catch (error) {
          firstError ??= error;
        }
      }
      if (firstError) {
        throw firstError;
      }
    }

    function dispose() {
      if (disposed) {
        return;
      }
      const ownedPages = Array.from(pages.values());
      pages.clear();
      disposed = true;
      let firstError = null;
      for (const page of ownedPages) {
        try {
          disposePage(page);
        } catch (error) {
          firstError ??= error;
        }
      }
      if (firstError) {
        throw firstError;
      }
    }

    return Object.freeze({
      get,
      peek,
      put,
      remove,
      clear,
      dispose,
      get size() {
        return pages.size;
      },
      keys: () => Array.from(pages.keys()),
    });
  }

  /**
   * @param {{rowHeight: number, maxRows: number, overscanRows: number, rebasePx: number}} options
   * @returns {MetabrowserGitHistoryVirtualWindow}
   */
  function createVirtualWindow(options) {
    const rowHeight = integer(options.rowHeight, "rowHeight");
    const maxRows = integer(options.maxRows, "maxRows");
    const overscanRows = integer(options.overscanRows, "overscanRows", { allowZero: true });
    const rebasePx = integer(options.rebasePx, "rebasePx");
    const segmentCapacity = Math.floor(rebasePx / rowHeight);
    if (segmentCapacity < maxRows) {
      throw new RangeError("rebasePx must hold at least maxRows fixed-height rows");
    }

    let rowCount = 0;
    let segmentStart = 0;
    let disposed = false;

    function assertLive() {
      if (disposed) {
        throw new Error("Git history virtual window is disposed");
      }
    }

    /** @param {number} nextCount */
    function setRowCount(nextCount) {
      assertLive();
      rowCount = integer(nextCount, "rowCount", { allowZero: true });
      const segmentRows = Math.min(rowCount, segmentCapacity);
      segmentStart = clamp(segmentStart, 0, Math.max(0, rowCount - segmentRows));
    }

    /**
     * @param {number} scrollTop
     * @param {number} viewportHeight
     * @returns {{scrollTop: number, rebased: boolean}}
     */
    function maybeRebase(scrollTop, viewportHeight) {
      const segmentRows = Math.min(rowCount, segmentCapacity);
      if (segmentRows === 0 || rowCount <= segmentCapacity) {
        if (segmentStart !== 0) {
          segmentStart = 0;
          return { scrollTop: Math.max(0, scrollTop), rebased: true };
        }
        return { scrollTop: Math.max(0, scrollTop), rebased: false };
      }

      const segmentHeight = segmentRows * rowHeight;
      const boundedScrollTop = clamp(scrollTop, 0, Math.max(0, segmentHeight - viewportHeight));
      const logicalTop = segmentStart + Math.floor(boundedScrollTop / rowHeight);
      const pixelOffset = boundedScrollTop % rowHeight;
      const lowerTrigger = segmentHeight * 0.25;
      const upperTrigger = segmentHeight * 0.75;
      const nearEarlierEdge = segmentStart > 0 && boundedScrollTop < lowerTrigger;
      const segmentEnd = segmentStart + segmentRows;
      const nearLaterEdge =
        segmentEnd < rowCount && boundedScrollTop + viewportHeight > upperTrigger;
      if (!nearEarlierEdge && !nearLaterEdge) {
        return { scrollTop: boundedScrollTop, rebased: false };
      }

      const visibleRows = Math.max(1, Math.ceil(viewportHeight / rowHeight));
      const targetStart = clamp(
        logicalTop - Math.floor((segmentRows - visibleRows) / 2),
        0,
        rowCount - segmentRows,
      );
      if (targetStart === segmentStart) {
        return { scrollTop: boundedScrollTop, rebased: false };
      }
      segmentStart = targetStart;
      return {
        scrollTop: (logicalTop - segmentStart) * rowHeight + pixelOffset,
        rebased: true,
      };
    }

    /**
     * @param {number} scrollTop
     * @param {number} viewportHeight
     * @returns {MetabrowserGitHistoryWindowRange}
     */
    function read(scrollTop, viewportHeight) {
      assertLive();
      const height = Math.max(rowHeight, Number.isFinite(viewportHeight) ? viewportHeight : 0);
      const rebase = maybeRebase(Math.max(0, scrollTop), height);
      const segmentRows = Math.min(rowCount, segmentCapacity);
      const segmentEnd = segmentStart + segmentRows;
      const segmentHeightPx = segmentRows * rowHeight;
      const localScrollTop = clamp(rebase.scrollTop, 0, Math.max(0, segmentHeightPx - height));
      const visibleStart = clamp(
        segmentStart + Math.floor(localScrollTop / rowHeight),
        segmentStart,
        segmentEnd,
      );
      const unclampedVisibleEnd = segmentStart + Math.ceil((localScrollTop + height) / rowHeight);
      const visibleEnd = clamp(
        unclampedVisibleEnd,
        visibleStart,
        Math.min(segmentEnd, visibleStart + maxRows),
      );
      const visibleRows = visibleEnd - visibleStart;
      const extraBudget = Math.max(0, maxRows - Math.min(maxRows, visibleRows));
      let before = Math.min(overscanRows, Math.floor(extraBudget / 2), visibleStart - segmentStart);
      let after = Math.min(overscanRows, extraBudget - before, segmentEnd - visibleEnd);
      const unused = extraBudget - before - after;
      if (unused > 0) {
        const beforeRoom = visibleStart - segmentStart - before;
        const moreBefore = Math.min(unused, beforeRoom, overscanRows - before);
        before += moreBefore;
        after += Math.min(
          unused - moreBefore,
          segmentEnd - visibleEnd - after,
          overscanRows - after,
        );
      }
      const start = visibleStart - before;
      const end = Math.min(segmentEnd, visibleEnd + after, start + maxRows);

      return Object.freeze({
        start,
        end,
        visibleStart,
        visibleEnd,
        segmentStart,
        segmentEnd,
        segmentHeightPx,
        topSpacerPx: (start - segmentStart) * rowHeight,
        bottomSpacerPx: (segmentEnd - end) * rowHeight,
        scrollTop: localScrollTop,
        rebased: rebase.rebased,
      });
    }

    /**
     * @param {number} ordinal
     * @param {number} viewportHeight
     * @param {"nearest" | "start" | "center" | "end"} [align]
     */
    function scrollTopForOrdinal(ordinal, viewportHeight, align = "nearest") {
      assertLive();
      if (rowCount === 0) {
        return 0;
      }
      const target = clamp(integer(ordinal, "ordinal", { allowZero: true }), 0, rowCount - 1);
      const segmentRows = Math.min(rowCount, segmentCapacity);
      if (target < segmentStart || target >= segmentStart + segmentRows) {
        segmentStart = clamp(
          target - Math.floor(segmentRows / 2),
          0,
          Math.max(0, rowCount - segmentRows),
        );
      }
      const height = Math.max(rowHeight, viewportHeight);
      const rowTop = (target - segmentStart) * rowHeight;
      const maximum = Math.max(0, segmentRows * rowHeight - height);
      if (align === "start") {
        return clamp(rowTop, 0, maximum);
      }
      if (align === "center") {
        return clamp(rowTop - (height - rowHeight) / 2, 0, maximum);
      }
      if (align === "end") {
        return clamp(rowTop - height + rowHeight, 0, maximum);
      }
      return clamp(rowTop, 0, maximum);
    }

    function dispose() {
      disposed = true;
      rowCount = 0;
      segmentStart = 0;
    }

    return Object.freeze({
      read,
      setRowCount,
      scrollTopForOrdinal,
      dispose,
      get rowCount() {
        return rowCount;
      },
      get segmentCapacity() {
        return segmentCapacity;
      },
    });
  }

  window.MetabrowserGitHistoryWindow = Object.freeze({
    createPageCache,
    createVirtualWindow,
  });
})();
