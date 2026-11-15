// The navigation toolbars' wrap rule (docs/design-system.md, "Navigation Toolbars Wrap"),
// laid out by a real engine and judged against the rule. The Chrome sessions that open
// each tab import it: tests/dom/files-tab-chrome.mjs (the Files filter row),
// tests/dom/github-pulls-stacks-chrome.mjs (the Pulls filters), and
// tests/dom/nav-metadata-chrome.mjs (the Commits tally and the tab bar).
//
// `sweep` lays the navigation pane out at every width from the narrowest it drags to,
// 180 px, which leaves its toolbars 179 (the pane's 1 px border), up to `WIDEST`, and reads
// one toolbar's units at each: the row's controls in order, or a cluster's chips in place
// of the cluster, which is one control drawn over several lines. Layout is synchronous,
// so one page call reads every width. `judge` holds what it read to the rule:
//
// - nothing is cut: every unit lies inside its row's content box, inside the pane, and
//   whole (no control's own box cuts its text short);
// - the row breaks where the rule says: one line exactly while the units' widths and the
//   gaps between them fit the row, and otherwise lines filled in order, each as full as
//   it can be (the next unit would not fit on it), so a unit moves down only when it must;
// - a trailing unit, which ends its line with an auto margin, is last and ends the row;
// - the lines are spaced by the tokens: the first `pad` below the toolbar's top, each
//   `line` tall, each `gap` below the one before, and the toolbar is its lines and the
//   gaps and its rule, and nothing else.
//
// Widths are the toolbar's own, which is the pane's content width: 299 at the default
// pane and 179 at the narrowest.

/** The widest toolbar the sweep reads; every toolbar fits one line well before it. */
export const WIDEST = 420;
/** The narrowest: the pane's 180 px minimum, less its 1 px border. */
export const NARROWEST = 179;
// Layout lands on fractions of a pixel; under half a pixel is not a different place.
const TOLERANCE = 0.5;
// Whether controls fit a line is exact: a line a 64th of a pixel short wraps. The widths
// are read in layout's own unit, so their sum is exact too.
const FIT_EPSILON = 0.001;

export const WIDTHS = Array.from(
  { length: WIDEST - NARROWEST + 1 },
  (_, index) => NARROWEST + index,
);

/**
 * In the page: lay the pane out at each width and read one toolbar.
 *
 * `spec.bar` is the toolbar, whose box and bottom rule bound it; `spec.row` the element
 * whose children are its controls; `spec.fit` names a row whose joined groups are fitted
 * at each width before it is read (filter-controls.js, `fitJoinedGroups`), as the row's
 * observer does a frame later; and `spec.tokens` maps a rule's spacing to CSS lengths the
 * page resolves, such as `var(--nav-toolbar-gap)`.
 */
export const SWEEP = `(spec) => {
  const pane = document.querySelector(".tree-pane");
  const saved = [pane.style.width, pane.style.minWidth];
  // Layout's own unit, a 64th of a pixel, so a sum of widths is as exact as the layout's.
  const round = (value) => Math.round(value * 64) / 64;
  const px = (value) => parseFloat(value) || 0;
  const resolve = (length) => {
    const probe = document.createElement("div");
    probe.style.cssText = "position: absolute; visibility: hidden; height: " + length;
    pane.append(probe);
    const value = probe.getBoundingClientRect().height;
    probe.remove();
    return round(value);
  };
  const tokens = Object.fromEntries(
    Object.entries(spec.tokens).map(([name, length]) => [name, resolve(length)]),
  );
  const fitter = window.metabrowser?.filterControls;
  const label = (el) =>
    el.dataset.chipValue || el.dataset.chipMenu || el.dataset.chipKey || el.dataset.tab ||
    (el.matches(".filter-check") ? "check:" + (el.querySelector("[data-chip-check]")?.dataset.chipCheck ?? "") : "") ||
    [...el.classList].filter((name) => !name.startsWith("mb-")).at(-1) || el.tagName.toLowerCase();
  const rows = [];
  for (const width of spec.widths) {
    pane.style.minWidth = "0";
    pane.style.width = width + 1 + "px";
    const row = document.querySelector(spec.row);
    if (spec.fit && fitter) fitter.fitJoinedGroups(row);
    const bar = document.querySelector(spec.bar);
    const barBox = bar.getBoundingClientRect();
    const barStyle = getComputedStyle(bar);
    const rowBox = row.getBoundingClientRect();
    const rowStyle = getComputedStyle(row);
    const left = rowBox.left + px(rowStyle.borderLeftWidth) + px(rowStyle.paddingLeft);
    const right = rowBox.right - px(rowStyle.borderRightWidth) - px(rowStyle.paddingRight);
    const paneBox = pane.getBoundingClientRect();
    const paneRight = paneBox.right - px(getComputedStyle(pane).borderRightWidth);
    const units = [];
    for (const child of row.children) {
      if (child.getClientRects().length === 0 || getComputedStyle(child).position === "absolute") continue;
      const cluster = child.matches(".chip-group") && getComputedStyle(child).flexWrap === "wrap";
      for (const el of cluster ? child.children : [child]) {
        const box = el.getBoundingClientRect();
        // Cut short: a box narrower than what it holds, clipped or spilling.
        const cut = [el, ...el.querySelectorAll("*")].some(
          (node) => node.clientWidth > 0 && node.scrollWidth > node.clientWidth + 1,
        );
        units.push({
          name: label(el),
          cluster,
          left: round(box.left - left),
          right: round(box.right - left),
          width: round(box.width),
          top: round(box.top - barBox.top),
          bottom: round(box.bottom - barBox.top),
          cut,
        });
      }
    }
    rows.push({
      width: round(barBox.width),
      content: round(right - left),
      paneRight: round(paneRight - left),
      height: round(barBox.height),
      rule: round(px(barStyle.borderBottomWidth)),
      fit: row.querySelector(".chip-group[data-layout='joined']")?.getAttribute("data-fit") ?? null,
      units,
    });
  }
  pane.style.width = saved[0];
  pane.style.minWidth = saved[1];
  return { tokens, rows };
}`;

/**
 * The units of one sweep row as lines: units sharing a top, in order of their tops and,
 * within a line, of their left edges.
 * @param {{units: Array<{name: string, top: number, bottom: number, left: number}>}} row
 */
export function linesOf(row) {
  const lines = [];
  for (const unit of [...row.units].sort((a, b) => a.top - b.top || a.left - b.left)) {
    const line = lines.find((candidate) => Math.abs(candidate.top - unit.top) <= TOLERANCE);
    if (line) {
      line.units.push(unit);
      line.bottom = Math.max(line.bottom, unit.bottom);
    } else {
      lines.push({ top: unit.top, bottom: unit.bottom, units: [unit] });
    }
  }
  for (const line of lines) {
    line.units.sort((a, b) => a.left - b.left);
  }
  return lines;
}

/**
 * Hold a sweep to the rule. `rule` gives the spacing in page pixels as `sweep` resolved
 * it: `pad` above the first line and below the last, `line` each line's height, `gap`
 * between lines, `column` between units on a line, `cluster` between a cluster's chips
 * on a line, the `trailing` unit that ends the row if it has one, and any `overlap` its
 * last line lends the toolbar's rule (a tab's 1 px). Returns the failures, empty when the
 * sweep keeps the rule, and the width from which the row is one line.
 *
 * @param {string} name
 * @param {{rows: any[]}} measured
 * @param {{pad: number, line: number, gap: number, column: number, cluster?: number,
 *          trailing?: string, overlap?: number}} rule
 */
export function judge(name, measured, rule) {
  const failures = [];
  const fail = (width, message) => failures.push(`${name} at ${width} px: ${message}`);
  const near = (a, b) => Math.abs(a - b) <= TOLERANCE;
  let oneLineFrom = null;
  for (const row of measured.rows) {
    const lines = linesOf(row);
    const at = row.width;
    // Nothing is cut: inside the row, inside the pane, and whole.
    for (const unit of row.units) {
      if (unit.left < -TOLERANCE || unit.right > row.content + TOLERANCE) {
        fail(
          at,
          `${unit.name} runs outside its row (${unit.left} to ${unit.right} of ${row.content})`,
        );
      }
      if (unit.right > row.paneRight + TOLERANCE) {
        fail(at, `${unit.name} runs past the pane (${unit.right} of ${row.paneRight})`);
      }
      if (unit.cut) {
        fail(at, `${unit.name} is cut short`);
      }
    }
    // In order: reading the lines gives the controls' order, a cluster's chips in its place.
    const read = lines.flatMap((line) => line.units.map((unit) => unit.name));
    const order = row.units.map((unit) => unit.name);
    if (JSON.stringify(read) !== JSON.stringify(order)) {
      fail(at, `the lines read ${read.join(", ")}, not the controls' order ${order.join(", ")}`);
    }
    // One line exactly while the units and the gaps between them fit the row.
    const natural =
      row.units.reduce((sum, unit) => sum + unit.width, 0) +
      row.units
        .slice(1)
        .reduce(
          (sum, unit, index) =>
            sum +
            (unit.cluster && row.units[index].cluster
              ? (rule.cluster ?? rule.column)
              : rule.column),
          0,
        );
    const anyCluster = row.units.some((unit) => unit.cluster);
    if (!anyCluster && natural <= row.content + FIT_EPSILON !== (lines.length === 1)) {
      fail(at, `${lines.length} lines where the controls are ${natural} px of ${row.content}`);
    }
    if (lines.length === 1 && oneLineFrom === null) {
      oneLineFrom = at;
    } else if (lines.length > 1) {
      oneLineFrom = null;
    }
    // Each line as full as it can be: its first unit would not have fit on the line before.
    for (let index = 1; index < lines.length; index += 1) {
      const before = lines[index - 1];
      const first = lines[index].units[0];
      const last = before.units.at(-1);
      // A cluster fills the lines it is drawn over: what follows it starts a line of its own.
      if (last.cluster && !first.cluster) {
        continue;
      }
      const used = before.units.at(-1).right - before.units[0].left;
      const spacing = first.cluster && last.cluster ? (rule.cluster ?? rule.column) : rule.column;
      if (used + spacing + first.width <= row.content - FIT_EPSILON) {
        fail(
          at,
          `${first.name} moved down though ${used} + ${spacing} + ${first.width} fit ${row.content}`,
        );
      }
    }
    // A trailing unit is last and ends the row, on whichever line it is.
    if (rule.trailing) {
      const last = lines.at(-1)?.units.at(-1);
      if (last?.name !== rule.trailing) {
        fail(at, `${rule.trailing} is not the row's last control (${last?.name})`);
      } else if (!near(last.right, row.content)) {
        fail(at, `${rule.trailing} ends at ${last.right}, not the row's end ${row.content}`);
      }
    }
    // The lines are spaced by the tokens.
    lines.forEach((line, index) => {
      const top = rule.pad + index * (rule.line + rule.gap);
      if (!near(line.top, top) || !near(line.bottom - line.top, rule.line)) {
        fail(
          at,
          `line ${index + 1} spans ${line.top} to ${line.bottom}, not ${top} to ${top + rule.line}`,
        );
      }
    });
    const height =
      2 * rule.pad +
      lines.length * rule.line +
      (lines.length - 1) * rule.gap +
      row.rule -
      (rule.overlap ?? 0);
    if (!near(row.height, height)) {
      fail(at, `the toolbar is ${row.height} px for ${lines.length} lines, not ${height}`);
    }
  }
  return { failures, oneLineFrom };
}
