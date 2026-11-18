// One hover for File Overview's population bars, the legend under them, and the
// Details table's rows.
//
// A segment of a tally bar and the legend entry that names its family are two
// handles on the bars, so they share one hover rather than each keeping its own
// (docs/design-system.md, "Aggregate Distributions"). The hover marks what its
// handle names. A segment names one value, the family's share of its own row, so
// pointing at it lifts and grows that segment alone: its tooltip is that value's,
// and lifting the family's other marks would say it describes them too. A legend
// entry names the family, so pointing at it lifts and grows the family's mark in
// every bar on screen: its segment in each tally row, and its row's bar in the
// Details table while that is open. Either way there is one tooltip, one
// segment's, anchored on the handle the pointer is on: for an entry, the family's
// segment in the tally row the legend's shares are of. So the hover is a row, a
// family, and what it marks, not a family alone. The bars and the Details table
// draw the hover; the segments and the legend entries only say where the pointer
// is.
//
// `enter` and `leave` are what the pointer says. `leave` lets go only of the
// handle it names, so a leave that arrives after the pointer has already entered
// another handle does not take that one away. `clear` is what a repaint says: the
// segment the hover was drawn on is gone, and its tooltip with it. `current` is
// what the repaint reads first, so it can draw again a hover whose handle outlives
// it, as a legend entry outlives a repaint of the bars.

/** @typedef {"all" | "files" | "ignored"} DistributionPopulation */
/**
 * What the hover marks: `self`, the one mark the pointer is on, as a segment is;
 * `family`, every mark of the family on screen, as a legend entry naming the family
 * does. Either way the family's legend entry is marked too.
 *
 * @typedef {"self" | "family"} DistributionHoverMarks
 */
/**
 * A family, the handle the pointer is on, and what the hover marks. *key* names the
 * family. For a legend entry, *population* names the tally row whose segment of the
 * family gives the tooltip, the row the legend's shares are of; for a segment, the row
 * it is in. The tooltip is anchored on *anchor*, so it sits by what the reader points at.
 *
 * @typedef {Readonly<{population: DistributionPopulation, key: string, anchor: Element, marks: DistributionHoverMarks}>} DistributionHoverTarget
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
    left?.anchor === right?.anchor &&
    left?.marks === right?.marks
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
      ? Object.freeze({
          population: next.population,
          key: next.key,
          anchor: next.anchor,
          marks: next.marks,
        })
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
