// The file-type legend: GitHub's Languages box in the distribution's colors, a dot, the
// type, and its share for each entry the rollup's legend names. File Overview and the
// Treemap draw the same one, from the same entries (file-type-summary-model.js,
// buildFileTypeLegend), and both bind it to the one hover their marks share
// (distribution-hover.js).
//
// A family's entry is a handle on that family's marks: pointing at it enters a hover that
// marks every mark of the family on screen, which the views draw on their own marks, and
// one tooltip, which the population bars show (folder-totals.js). The entry naming the
// hovered family is marked too, whichever handle holds the hover, the entry or one of the
// family's marks, so the key answers with what it keys: its dot lifts and shimmers, and
// its name takes the family's ink (file_type_summary.css). Other names no one mark: it is
// the families too small to name and the files no family claims, so it answers no hover
// and is never marked. No entry is a tab stop, as no mark is (docs/design-system.md,
// "Aggregate Distributions").

/**
 * Bind *list*, an empty `<ul class="file-type-summary-legend">`, to *hover*. The legend
 * is rebuilt whole on each update: it is at most a handful of items with nothing
 * focusable in them, so there is no state in it to keep but the hover an entry under the
 * pointer holds, which it lets go of first, and the mark the hover puts on its family's
 * entry, which it draws again last.
 *
 * @param {HTMLElement} list
 * @param {{paint(element: HTMLElement, key: string): void}} palette
 * @param {DistributionHover} hover
 */
export function createDistributionLegend(list, palette, hover) {
  /** @type {DistributionHoverTarget | null} */
  let held = null;
  /** @type {HTMLElement | null} */
  let marked = null;

  /**
   * Let go of the hover an entry under the pointer holds, as the entry is about to leave
   * the document: a removed element never hears the pointer leave it, so without this the
   * marks it named would stay lifted and its tooltip up.
   */
  function release() {
    if (held) {
      hover.leave(held);
      held = null;
    }
  }

  /** Mark the entry naming the hovered family, whichever handle holds the hover. */
  function draw() {
    if (marked) {
      delete marked.dataset.hovered;
      marked = null;
    }
    const target = hover.current();
    if (!target) {
      return;
    }
    const entries = /** @type {Array<HTMLElement>} */ ([...list.children]);
    const entry = entries.find((item) => item.dataset.legendKey === target.key);
    if (entry) {
      entry.dataset.hovered = "";
      marked = entry;
    }
  }
  const unsubscribe = hover.subscribe(draw);

  /**
   * @param {ReadonlyArray<SummaryLegendEntry>} entries
   * @param {DistributionPopulation} population The tally row the entries' shares are of,
   *   Total while Show ignored is on and Files while it is off: the row whose segment of
   *   a family gives an entry's tooltip.
   */
  function update(entries, population) {
    release();
    marked = null;
    list.hidden = entries.length === 0;
    list.replaceChildren(
      ...entries.map((entry) => {
        const item = document.createElement("li");
        item.className = "file-type-summary-legend-item";
        item.dataset.legendKey = entry.key;
        // The entry carries its family's color, which the dot inherits, and which its
        // name takes as ink while the hover marks it.
        palette.paint(item, entry.paletteKey);
        const swatch = document.createElement("span");
        swatch.className = "file-type-summary-legend-swatch";
        swatch.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.className = "file-type-summary-legend-label";
        label.textContent = entry.label;
        const percent = document.createElement("span");
        percent.className = "file-type-summary-legend-percent";
        percent.textContent = entry.percent;
        item.append(swatch, label, percent);
        if (entry.kind === "family") {
          /** @type {DistributionHoverTarget} */
          const target = Object.freeze({
            population,
            key: entry.key,
            anchor: item,
            marks: /** @type {const} */ ("family"),
          });
          // The views redraw their marks whenever their data changes, and this entry
          // outlives those draws, so they draw its hover again themselves
          // (folder-totals.js, render).
          item.addEventListener("mouseenter", () => {
            held = target;
            hover.enter(target);
          });
          item.addEventListener("mouseleave", () => {
            held = null;
            hover.leave(target);
          });
        }
        return item;
      }),
    );
    // A hover held from a family's mark outlives the legend, so its new entry is marked.
    draw();
  }

  /** Let go of the hover and stop listening; the list is the caller's to remove. */
  function dispose() {
    release();
    unsubscribe();
    if (marked) {
      delete marked.dataset.hovered;
      marked = null;
    }
  }

  return Object.freeze({ list, update, release, dispose });
}

/** @typedef {ReturnType<typeof createDistributionLegend>} DistributionLegend */
/** @typedef {import("./distribution-hover.js").DistributionHover} DistributionHover */
/** @typedef {import("./distribution-hover.js").DistributionHoverTarget} DistributionHoverTarget */
/** @typedef {import("./distribution-hover.js").DistributionPopulation} DistributionPopulation */
/** @typedef {{key: string, label: string, paletteKey: string, kind: "family" | "other", value: number, percent: string, share: number}} SummaryLegendEntry */
