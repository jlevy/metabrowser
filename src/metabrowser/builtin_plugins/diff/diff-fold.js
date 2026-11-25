// The diff's fold expander: the blue bar that stands for a run of rows withheld from a
// file and opens to them (docs/design-system.md, "Fold Expanders"). A code file's long
// changed run and the unchanged lines between its hunks (diff-view.js), and a rendered
// Markdown file's run of unchanged blocks (diff-markdown.js), are folds of one kind, so
// all draw this bar and open and close alike: the bar comes first, the group it controls
// follows it, and the group grows from nothing when it opens. The bar owns its state; what
// the group holds is its caller's, which fills the group when it opens and empties it when
// it closes.

/**
 * The shell's icon of that name, or nothing outside the shell. The diff view's glyphs
 * take theirs from here.
 *
 * @param {string} name
 * @returns {string}
 */
export function shellIcon(name) {
  const shell = /** @type {{metabrowser?: {icons?: Record<string, string>}}} */ (
    /** @type {unknown} */ (globalThis)
  );
  return shell.metabrowser?.icons?.[name] ?? "";
}

/**
 * @typedef {object} FoldExpander
 * @property {HTMLButtonElement} control The bar, which goes right before *group*.
 * @property {HTMLElement} group What the bar shows and hides.
 * @property {() => boolean} expanded
 * @property {(next: boolean) => void} set Open or close it, as a click does, and say so.
 * @property {() => void} relabel Say *label* again, for a count that changed in the state
 *   it is in.
 */

/**
 * A fold's bar and the group it controls, open when *expanded*.
 *
 * *label* names the bar in each state: what the closed bar holds, then the inverse
 * ("40 more changed lines", "Hide 40 lines"). *detail*, where a fold has one, follows the
 * label in the bar's own sans face and the plain separator's muted tone, as a hunk's
 * separator, its ranges between `@@` marks, does where its bar stands (styles.css,
 * `.diff-fold-detail`).
 * *onToggle* runs after every change of state, a click's or `set`'s, with the new state,
 * and fills or empties the group; a fold drawn open calls it once the caller has the bar,
 * to fill the group (`open` is for that).
 *
 * @param {{
 *   id: string,
 *   expanded: boolean,
 *   label: (expanded: boolean) => string,
 *   onToggle: (expanded: boolean) => void,
 *   groupClass?: string,
 *   detail?: string,
 * }} options
 * @returns {FoldExpander}
 */
export function foldExpander({ id, expanded, label, onToggle, groupClass = "", detail = "" }) {
  let open = expanded;
  const group = document.createElement("div");
  group.className = `diff-fold-group${groupClass ? ` ${groupClass}` : ""}`;
  group.id = id;
  const control = document.createElement("button");
  control.className = "fold-expander diff-fold-control disclosure-toggle";
  control.type = "button";
  control.setAttribute("aria-controls", id);
  // Its glyph, the expand/contract pair, is the shell's `.fold-expander`'s, drawn from
  // `aria-expanded`, so the bar holds only its words.
  const text = document.createElement("span");
  text.className = "diff-fold-label";
  control.append(text);
  if (detail !== "") {
    const said = document.createElement("span");
    said.className = "diff-fold-detail";
    said.textContent = detail;
    control.append(said);
  }

  function draw() {
    control.setAttribute("aria-expanded", String(open));
    group.classList.toggle("diff-fold-collapsed", !open);
    text.textContent = label(open);
  }

  /** @param {boolean} next */
  function set(next) {
    if (next === open) {
      return;
    }
    open = next;
    draw();
    onToggle(open);
  }

  control.addEventListener("click", (event) => {
    // The bar above owns clicks on the file section; a fold is its own control and must
    // not also collapse the whole file.
    event.stopPropagation();
    set(!open);
  });
  draw();
  return { control, group, expanded: () => open, set, relabel: draw };
}
