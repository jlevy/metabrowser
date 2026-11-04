// Variable-height PR rows: only the viewport, overscan and protected anchors are mounted.
// Heights include an expanded file tree. Unmounted rows retain their measured space, so
// bringing a distant focused/current row into the document does not collapse the list.

/**
 * @param {{estimate: number, overscan: number}} options
 */
export function createPullsWindow(options) {
  /** @type {number[]} */
  let rows = [];
  /** @type {Map<number, number>} */
  let indices = new Map();
  /** @type {Map<number, number>} */
  const measured = new Map();
  let offsets = [0];
  let dirty = false;

  function positions() {
    if (dirty) {
      offsets = [0];
      for (const number of rows) {
        offsets.push(offsets[offsets.length - 1] + (measured.get(number) ?? options.estimate));
      }
      dirty = false;
    }
    return offsets;
  }

  /** First row whose bottom lies after a coordinate. @param {number} y */
  function at(y) {
    const prefix = positions();
    let low = 0;
    let high = rows.length;
    while (low < high) {
      const mid = (low + high) >>> 1;
      if (prefix[mid + 1] <= y) {
        low = mid + 1;
      } else {
        high = mid;
      }
    }
    return low;
  }

  return Object.freeze({
    /** @param {number[]} next */
    setRows(next) {
      rows = next;
      indices = new Map(next.map((number, index) => [number, index]));
      for (const number of measured.keys()) {
        if (!indices.has(number)) {
          measured.delete(number);
        }
      }
      dirty = true;
    },
    /** @param {number} number @param {number} height */
    measure(number, height) {
      if (!indices.has(number) || !Number.isFinite(height) || height <= 0) {
        return false;
      }
      const previous = measured.get(number) ?? options.estimate;
      if (Math.abs(previous - height) < 0.5) {
        return false;
      }
      measured.set(number, height);
      dirty = true;
      return true;
    },
    /** @param {number} number */
    offset(number) {
      const index = indices.get(number);
      return index === undefined ? null : positions()[index];
    },
    /** @param {number} top @param {number} bottom @param {(number | null)[]} protectedRows */
    range(top, bottom, protectedRows = []) {
      const prefix = positions();
      const start = Math.max(0, at(top) - options.overscan);
      const end = Math.min(rows.length, at(bottom) + options.overscan + 1);
      const wanted = new Set(Array.from({ length: end - start }, (_, index) => start + index));
      for (const number of protectedRows) {
        const index = number === null ? undefined : indices.get(number);
        if (index !== undefined) {
          wanted.add(index);
        }
      }
      const order = [...wanted].sort((left, right) => left - right);
      /** @type {({kind: "row", number: number, index: number} | {kind: "gap", start: number, end: number, height: number})[]} */
      const result = [];
      let previous = 0;
      for (const index of order) {
        if (index > previous) {
          result.push({
            kind: "gap",
            start: previous,
            end: index,
            height: prefix[index] - prefix[previous],
          });
        }
        result.push({ kind: "row", number: rows[index], index });
        previous = index + 1;
      }
      if (previous < rows.length) {
        result.push({
          kind: "gap",
          start: previous,
          end: rows.length,
          height: prefix[rows.length] - prefix[previous],
        });
      }
      return result;
    },
  });
}
