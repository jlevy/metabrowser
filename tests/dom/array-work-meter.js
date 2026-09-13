// Deterministic cost meter for production modules evaluated in a vm context.
//
// Counts every array element the context's `push`, `slice`, and `splice`
// touch: pushed items, copied items, and for `splice` the removed, inserted,
// and shifted elements. These are the primitives the Quick File catalog uses
// to maintain its ordered projection, so a count per operation is a
// machine-independent statement of its asymptotic cost. A quadratic insertion
// into a 300,000-row projection touches tens of millions of elements; one
// linear pass touches about 300,000.
//
// Contract sessions assert these counts instead of wall-clock durations, which
// vary with machine load (see docs/large-content-rendering.md). Real-time
// responsiveness budgets stay with the headed performance harness.

const vm = require("node:vm");

/**
 * Meter the array primitives of one vm context. Install after
 * `vm.createContext` and before the code under test runs.
 * @param {object} context
 * @returns {{ read(): number }}
 */
function installArrayWorkMeter(context) {
  const prototype = vm.runInContext("Array.prototype", context);
  const { push, slice, splice } = prototype;
  let elements = 0;

  prototype.push = function meteredPush(...items) {
    elements += items.length;
    return push.apply(this, items);
  };
  prototype.slice = function meteredSlice(...args) {
    const copy = slice.apply(this, args);
    elements += copy.length;
    return copy;
  };
  prototype.splice = function meteredSplice(...args) {
    const length = this.length;
    const relativeStart = Math.trunc(Number(args[0]) || 0);
    const start =
      relativeStart < 0 ? Math.max(length + relativeStart, 0) : Math.min(relativeStart, length);
    let deleted = 0;
    if (args.length === 1) {
      deleted = length - start;
    } else if (args.length > 1) {
      deleted = Math.min(Math.max(Math.trunc(Number(args[1]) || 0), 0), length - start);
    }
    const inserted = Math.max(args.length - 2, 0);
    const shifted = inserted === deleted ? 0 : length - start - deleted;
    elements += deleted + inserted + shifted;
    return splice.apply(this, args);
  };

  return {
    read() {
      return elements;
    },
  };
}

module.exports = { installArrayWorkMeter };
