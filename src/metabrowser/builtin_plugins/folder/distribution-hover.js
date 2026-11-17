// One hover for File Overview's population bars and the legend under them.
//
// A segment of a tally bar and the legend entry that names its family are two
// handles on one mark, so they share one hover rather than each keeping its
// own: pointing at either one lifts and grows the segment and shows its
// tooltip, anchored on the handle the pointer is on, the entry or the segment
// (docs/design-system.md, "Aggregate Distributions"). The bars draw the hover;
// the segments and the legend entries only say where the pointer is. A legend
// entry names one tally row's segment, the row its shares are of, so the hover
// is a row and a family, not a family alone: the same family has a segment in
// each row.
//
// `enter` and `leave` are what the pointer says. `leave` lets go only of the
// handle it names, so a leave that arrives after the pointer has already entered
// another handle does not take that one away. `clear` is what a repaint says: the
// segment the hover was drawn on is gone, and its tooltip with it. `current` is
// what the repaint reads first, so it can draw again a hover whose handle outlives
// it, as a legend entry outlives a repaint of the bars.

/** @typedef {"all" | "files" | "ignored"} DistributionPopulation */
/**
 * A mark and the handle the pointer is on: the segment itself, or a legend entry naming
 * it. The tooltip is anchored on *anchor*, so it sits by what the reader points at.
 *
 * @typedef {Readonly<{population: DistributionPopulation, key: string, anchor: Element}>} DistributionHoverTarget
 */
/** @typedef {(current: DistributionHoverTarget | null, previous: DistributionHoverTarget | null) => void} DistributionHoverListener */
/** @typedef {{current: () => DistributionHoverTarget | null, enter: (target: DistributionHoverTarget) => void, leave: (target: DistributionHoverTarget) => void, clear: () => void, subscribe: (listener: DistributionHoverListener) => () => void}} DistributionHover */

/**
 * @param {DistributionHoverTarget | null} left
 * @param {DistributionHoverTarget | null} right
 */
function sameTarget(left, right) {
  return (
    left?.population === right?.population &&
    left?.key === right?.key &&
    left?.anchor === right?.anchor
  );
}

/** @returns {DistributionHover} */
export function createDistributionHover() {
  /** @type {DistributionHoverTarget | null} */
  let current = null;
  /** @type {Set<DistributionHoverListener>} */
  const listeners = new Set();

  /** @param {DistributionHoverTarget | null} next */
  function set(next) {
    // Moving within one handle changes nothing, so nothing is told: a tooltip holds
    // still while it is up. Moving from a segment onto its entry, or back, is a
    // change: the tooltip goes to the handle the pointer is now on.
    if (sameTarget(current, next)) {
      return;
    }
    const previous = current;
    current = next
      ? Object.freeze({ population: next.population, key: next.key, anchor: next.anchor })
      : null;
    for (const listener of [...listeners]) {
      listener(current, previous);
    }
  }

  return Object.freeze({
    current: () => current,
    /** @param {DistributionHoverTarget} target */
    enter(target) {
      set(target);
    },
    /** @param {DistributionHoverTarget} target */
    leave(target) {
      if (sameTarget(current, target)) {
        set(null);
      }
    },
    clear() {
      set(null);
    },
    /** @param {DistributionHoverListener} listener */
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  });
}
