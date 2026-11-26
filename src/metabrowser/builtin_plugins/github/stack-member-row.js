// A pull request's fields in their one order, the state icon, the title, the place in its
// stack, the number, and the author (docs/design-system.md, "One Order for a Pull Request's
// Fields"), drawn by one builder, `stackMemberRow`, on every row that names a pull request
// with them: a native stack's member, the member row of docs/design-system.md, "Stacks", on
// the stack menu of a pull request's page (`createStackMenu` in pull-page.js) and on the
// stack's own page (stack-page.js), and a Pulls row's run (pulls-panel.js). The order and the
// dots between the fields are the builder's, so no surface can draw them in another order;
// a surface chooses only its layout, the classes its stylesheet lays out and how the dots
// sit, from the two below.
//
// - `MEMBER_LINE`, one line: the title bold in text ink and cut short, and at the line's end,
//   together, the place, a muted dot, the number, and another dot and the author, the shell's
//   actor identity, "14/15 · #455 · jlevy". The whole title is the row's tip.
// - `PULLS_RUN`, a run that wraps in the text column, a dot before each field after the
//   title, the place's too: "title · 14/15 · #455 · jlevy". The fields after the title are
//   hidden from assistive technology and the row's link says them in words, in this order,
//   and the Pulls column shows no tooltips (docs/design-system.md, "Tooltips Add
//   Information").
//
// A member whose state is not known yet keeps the icon's slot, empty, so every member's title
// starts at one edge.
//
// A row that shows a pull request's readiness (mb-3n21; row-readiness.js) says it after the
// state, in words out of view after the state icon, as the icon says the state, and draws its
// glyph, hidden from assistive technology, where its layout puts it: at a line's end, after the
// author, in a cell as wide as the glyph, empty for a member with no readiness, so every
// member's fields end at one edge; and in a Pulls row, in its last line's readiness column, a
// cell the builder draws and the row places (`readiness`), with the label after the glyph.
// A surface that shows no readiness, as a guide's pull request row does not, passes none, and
// its row has neither.

import { readinessIcon } from "./pull-readiness.js";
import { pullStateIcon } from "./pull-state.js";

/**
 * A pull request's fields as a row shows them. `place` is its place in its stack, "14/15",
 * or null where it is in none; a row draws `placeNodes` for it where given, as a guide's row
 * and a Pulls row's run draw a place that names another stack (`namedStackPositionNodes` in
 * pull-stacks.js), and names it by `placeHint`, a line in its tip too. `readiness` is the
 * verdict a row draws (row-readiness.js), null for a pull request with none, and absent on a
 * surface that shows no readiness.
 *
 * @typedef {{
 *   number: number,
 *   place: string | null,
 *   placeNodes?: Array<Node | string>,
 *   placeHint?: string,
 *   title: string | null,
 *   state: import("./pull-state.js").PullState | null,
 *   author: {login: string, avatar: string | null} | null,
 *   readiness?: import("./pull-readiness.js").ShownReadiness | null,
 * }} StackMemberLine
 */

/**
 * How a surface lays the fields out: the classes of its parts, which its stylesheet lays out,
 * and whether they run as one wrapping flow (`flow`) or sit on one line, the title first and
 * the rest at its end. `row` is added to the element drawn into, and `copy`, in a line, wraps
 * the fields after the icon. `readiness` is the class of the readiness's cell, and
 * `readinessLabel` that of the label after its glyph, or null where the cell is the glyph
 * alone.
 *
 * @typedef {{
 *   flow: boolean,
 *   row: string | null,
 *   copy: string | null,
 *   title: string,
 *   place: string,
 *   number: string,
 *   by: string,
 *   readiness: string,
 *   readinessLabel: string | null,
 * }} MemberRowLayout
 */

/** A stack's member on one line, in the stack menu and on the stack's page. */
export const MEMBER_LINE = /** @type {MemberRowLayout} */ (
  Object.freeze({
    flow: false,
    row: "github-pull-stack-member",
    copy: "github-pull-stack-member-copy",
    title: "github-pull-stack-member-title",
    place: "github-pull-stack-member-position",
    number: "github-pull-stack-member-number",
    by: "github-pull-stack-member-by",
    readiness: "github-pull-stack-member-readiness",
    readinessLabel: null,
  })
);

/** A Pulls row's run, under its row's link (github/styles.css, `.github-pulls-heading`). */
export const PULLS_RUN = /** @type {MemberRowLayout} */ (
  Object.freeze({
    flow: true,
    row: null,
    copy: null,
    title: "github-pulls-title",
    place: "github-pulls-place",
    number: "github-pulls-number",
    by: "github-pulls-by",
    readiness: "github-pulls-readiness",
    readinessLabel: "github-pulls-readiness-label",
  })
);

/**
 * A row drawn into its element, its title and place, which a surface may mark, `readiness`,
 * the readiness's cell, which a run's surface places and a line places itself, and `show`,
 * which draws a pull request's fields into it.
 *
 * @typedef {{
 *   link: HTMLElement,
 *   title: HTMLElement,
 *   place: HTMLElement,
 *   readiness: HTMLElement,
 *   show(member: StackMemberLine): void,
 * }} StackMemberRow
 */

/**
 * Make *link* a row of a pull request's fields: the state icon, then the title, the place, the
 * number, and the author, which *identity* draws, in that order whatever the *layout*. A field
 * that is not known, a place where the pull request is in no stack, or an author not known or
 * with no *identity*, has neither its dot nor itself, not even the space before them. `show`
 * changes only what differs from the fields the row shows, so a row drawn again keeps its
 * nodes, and its author's avatar its image. A member not read yet is titled "Pull request
 * #N".
 *
 * @param {HTMLElement} link The element the row is drawn into: a member's link, or a Pulls
 *   row's run.
 * @param {(title: string) => Array<Node | string>} titleNodes The SDK's `titleNodes`.
 * @param {(login: string, avatar: string | null) => HTMLElement} [identity] The author's
 *   identity, `authorLabel` in pull-page.js.
 * @param {MemberRowLayout} [layout]
 * @returns {StackMemberRow}
 */
export function stackMemberRow(link, titleNodes, identity, layout = MEMBER_LINE) {
  const make = (/** @type {string} */ tag, /** @type {string} */ className) => {
    const element = document.createElement(tag);
    element.setAttribute("class", className);
    return element;
  };
  const dot = () => {
    const element = make("span", "github-pull-stack-dot");
    element.setAttribute("aria-hidden", "true");
    element.textContent = "·";
    return element;
  };
  // The dot before a field after the title. On a line, a space either side of it. In a run, a
  // no-break space before it and a text space after it, so the run breaks after the dot as
  // after a word and never before it (github/styles.css, `.github-pulls-heading`).
  const separator = () => {
    if (!layout.flow) {
      return [" ", dot(), " "];
    }
    const element = make("span", "github-pulls-sep");
    element.setAttribute("aria-hidden", "true");
    const mark = make("span", "github-pull-stack-dot");
    mark.textContent = "·";
    element.append("\u00a0", mark, " ");
    return [element];
  };
  const emptyIcon = () => {
    const element = make("span", "github-pull-state-icon");
    element.setAttribute("aria-hidden", "true");
    return element;
  };
  if (layout.row !== null) {
    link.classList.add(layout.row);
  }
  const title = make("span", layout.title);
  const number = make("span", layout.number);
  const by = make("span", layout.by);
  by.hidden = true;
  // A line's place is its bold position alone; a run's is its dot and its position, hidden in
  // no stack, and named for assistive technology by its hint.
  const place = make(layout.flow ? "span" : "strong", layout.place);
  const position = layout.flow ? make("span", "github-pull-stack-position") : place;
  /** @type {Node[]} */
  let authorSeparator = [];
  if (layout.flow) {
    place.setAttribute("role", "img");
    place.hidden = true;
    number.setAttribute("aria-hidden", "true");
    by.setAttribute("aria-hidden", "true");
    authorSeparator = /** @type {Node[]} */ (separator());
    for (const node of authorSeparator) {
      /** @type {HTMLElement} */ (node).hidden = true;
    }
  }
  const holder = layout.copy === null ? null : make("span", layout.copy);
  // The readiness: its words, out of view after the state icon, and its cell, hidden, which a
  // run's surface places and a line ends with, each there from the first line that carries a
  // readiness (`placeReadiness`).
  const spoken = make("span", "sr-only github-pull-readiness-said");
  const cell = make("span", layout.readiness);
  cell.setAttribute("aria-hidden", "true");
  let readinessPlaced = false;
  let icon = emptyIcon();
  // The fields after the icon. A run's place hides itself, its dot with it; a line's place and
  // the dot after it are laid out only while there is a place, so a pull request in no stack
  // reads "title #N" and never "title · #N".
  const lay = (/** @type {boolean} */ placed) => {
    const fields = layout.flow
      ? [title, place, ...separator(), number, ...authorSeparator, by]
      : [title, " ", ...(placed ? [place, ...separator()] : []), number, by];
    if (holder === null) {
      link.replaceChildren(icon, ...fields);
    } else {
      holder.replaceChildren(...fields);
    }
  };
  link.replaceChildren(icon, ...(holder === null ? [] : [holder]));
  lay(false);
  /** The readiness's words after the state icon, and, in a line, its cell at the line's end. */
  const placeReadiness = () => {
    link.insertBefore(spoken, icon.nextSibling);
    if (!layout.flow) {
      link.append(cell);
    }
    readinessPlaced = true;
  };
  /** @type {{words: string | null, place: string | null | undefined, state: StackMemberLine["state"] | undefined, author: string | null, readiness: string | null}} */
  const shown = { words: null, place: undefined, state: undefined, author: null, readiness: null };
  return {
    link,
    title,
    place,
    readiness: cell,
    show(member) {
      const words = member.title || `Pull request #${member.number}`;
      if (shown.words !== words) {
        title.replaceChildren(...titleNodes(words));
        if (!layout.flow) {
          link.setAttribute("data-tip-text", words);
        }
        shown.words = words;
      }
      const placed = member.place === null ? null : `${member.place}\n${member.placeHint ?? ""}`;
      if (shown.place !== placed) {
        if (layout.flow) {
          place.hidden = member.place === null;
          if (member.place === null) {
            place.replaceChildren();
            place.removeAttribute("aria-label");
          } else {
            position.replaceChildren(...(member.placeNodes ?? [member.place]));
            place.replaceChildren("\u00a0", dot(), " ", position);
            place.setAttribute("aria-label", member.placeHint ?? member.place);
          }
        } else {
          place.replaceChildren(...(member.placeNodes ?? [member.place ?? ""]));
          // A place whose stack nothing around the line names, as on a guide's row, says it
          // in its hint, which is its accessible name, as a run's is, and its tip.
          const hint = member.place === null ? null : (member.placeHint ?? null);
          if (hint === null) {
            place.removeAttribute("role");
            place.removeAttribute("aria-label");
            place.removeAttribute("data-tip-text");
          } else {
            place.setAttribute("role", "img");
            place.setAttribute("aria-label", hint);
            place.setAttribute("data-tip-text", hint);
          }
          const had = shown.place !== undefined && shown.place !== null;
          if (had !== (placed !== null)) {
            lay(placed !== null);
          }
        }
        shown.place = placed;
      }
      const numbered = `#${member.number}`;
      if (number.textContent !== numbered) {
        number.textContent = numbered;
      }
      if (shown.state !== member.state) {
        // Named, as every state icon is, since nothing else on the line says the state.
        const drawn = member.state === null ? emptyIcon() : pullStateIcon(member.state);
        link.insertBefore(drawn, icon);
        icon.remove();
        icon = drawn;
        shown.state = member.state;
      }
      const author = identity === undefined ? null : member.author;
      const said = author === null ? "" : `${author.login}\n${author.avatar ?? ""}`;
      if (shown.author !== said) {
        const drawn =
          author === null || identity === undefined ? null : identity(author.login, author.avatar);
        if (layout.flow) {
          by.replaceChildren(...(drawn === null ? [] : [drawn]));
          for (const node of authorSeparator) {
            /** @type {HTMLElement} */ (node).hidden = drawn === null;
          }
        } else {
          by.replaceChildren(...(drawn === null ? [] : [...separator(), drawn]));
        }
        by.hidden = drawn === null;
        shown.author = said;
      }
      if (member.readiness !== undefined) {
        if (!readinessPlaced) {
          placeReadiness();
        }
        const readiness = member.readiness;
        const drawnReadiness =
          readiness === null ? "" : `${readiness.verdict}\n${readiness.tone}\n${readiness.label}`;
        if (shown.readiness !== drawnReadiness) {
          // The words say the label, and the glyph, in the readiness's tone, and the label after
          // it are the cell's, hidden (github/styles.css, "A pull request's readiness").
          spoken.textContent = readiness === null ? "" : readiness.label;
          const glyph = readinessIcon(readiness, { named: false });
          /** @type {Node[]} */
          const parts = glyph === null ? [] : [glyph];
          if (readiness !== null && layout.readinessLabel !== null) {
            const label = make("span", layout.readinessLabel);
            label.textContent = readiness.label;
            parts.push(label);
          }
          cell.replaceChildren(...parts);
          shown.readiness = drawnReadiness;
        }
      }
    },
  };
}
