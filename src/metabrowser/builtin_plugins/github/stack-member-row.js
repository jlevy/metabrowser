// The Pulls sidebar, stack lists and menus, and Guided Review references share this order:
// state icon, wrapping title, stack position, author, readiness glyph, and PR number.

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

/** @typedef {{
 *   row?: string,
 *   title: string,
 *   place: string,
 *   number: string,
 *   by: string,
 *   readiness: string,
 * }} MemberRowLayout */

export const MEMBER_LINE = /** @type {MemberRowLayout} */ (
  Object.freeze({
    row: "github-pull-stack-member",
    title: "github-pull-stack-member-title",
    place: "github-pull-stack-member-position",
    number: "github-pull-stack-member-number",
    by: "github-pull-stack-member-by",
    readiness: "github-pull-stack-member-readiness",
  })
);

export const PULLS_RUN = /** @type {MemberRowLayout} */ (
  Object.freeze({
    title: "github-pulls-title",
    place: "github-pulls-place",
    number: "github-pulls-number",
    by: "github-pulls-by",
    readiness: "github-pulls-readiness",
  })
);

/** @typedef {{
 *   link: HTMLElement,
 *   title: HTMLElement,
 *   place: HTMLElement,
 *   end: HTMLElement,
 *   show(member: StackMemberLine): void,
 * }} StackMemberRow */

/**
 * Keep the title and its inline details in one wrapping column. The number and readiness
 * share the trailing column, aligned to the last line. A repaint changes only fields whose
 * values changed, preserving the avatar and the focused row.
 *
 * @param {HTMLElement} link
 * @param {(title: string) => Array<Node | string>} titleNodes
 * @param {(login: string, avatar: string | null) => HTMLElement} [identity]
 * @param {MemberRowLayout} [layout]
 * @returns {StackMemberRow}
 */
export function stackMemberRow(link, titleNodes, identity, layout = MEMBER_LINE) {
  const make = (/** @type {string} */ className) => {
    const element = document.createElement("span");
    element.setAttribute("class", className);
    return element;
  };
  const separator = () => {
    const mark = make("github-pull-stack-dot");
    mark.setAttribute("aria-hidden", "true");
    mark.textContent = "·";
    return ["\u00a0", mark, " "];
  };
  const emptyIcon = () => {
    const element = make("github-pull-state-icon");
    element.setAttribute("aria-hidden", "true");
    return element;
  };

  const sidebar = layout.row === undefined;
  if (layout.row !== undefined) {
    link.classList.add(layout.row);
  }
  let icon = emptyIcon();
  const copy = make("github-pull-row-copy");
  const title = make(layout.title);
  const place = make(layout.place);
  const position = make("github-pull-stack-position");
  place.hidden = true;
  const by = make(layout.by);
  by.hidden = true;
  copy.append(title, place, by);

  const end = make("github-pull-row-end");
  const number = make(layout.number);
  if (sidebar) {
    number.setAttribute("aria-hidden", "true");
    by.setAttribute("aria-hidden", "true");
  }
  end.append(number);
  if (sidebar) {
    place.classList.add("sr-only");
  } else {
    copy.append(" ", end);
  }
  link.replaceChildren(icon, copy);

  const spoken = make("sr-only github-pull-readiness-said");
  const cell = make(layout.readiness);
  cell.setAttribute("aria-hidden", "true");
  /** @type {{words?: string, place?: string, state?: StackMemberLine["state"], author?: string, readiness?: string}} */
  const shown = {};
  return {
    link,
    title,
    place,
    end,
    show(member) {
      const words = member.title || `Pull request #${member.number}`;
      if (words !== shown.words) {
        title.replaceChildren(...titleNodes(words));
        if (!sidebar) {
          link.setAttribute("data-tip-text", words);
        }
        shown.words = words;
      }

      const placeKey = JSON.stringify([member.place, member.placeHint]);
      if (placeKey !== shown.place) {
        place.hidden = member.place === null;
        position.replaceChildren(...(member.placeNodes ?? [member.place ?? ""]));
        place.replaceChildren(...(place.hidden ? [] : [...separator(), position]));
        if (member.placeHint || (sidebar && member.place !== null)) {
          const hint = member.placeHint ?? member.place ?? "";
          place.setAttribute("role", "img");
          place.setAttribute("aria-label", hint);
          if (!sidebar) {
            place.setAttribute("data-tip-text", hint);
          }
        } else {
          place.removeAttribute("role");
          place.removeAttribute("aria-label");
          place.removeAttribute("data-tip-text");
        }
        shown.place = placeKey;
      }

      const numbered = `#${member.number}`;
      if (numbered !== number.textContent) {
        number.textContent = numbered;
      }
      if (member.state !== shown.state) {
        const drawn = member.state === null ? emptyIcon() : pullStateIcon(member.state);
        link.insertBefore(drawn, icon);
        icon.remove();
        icon = drawn;
        shown.state = member.state;
      }

      const author = member.author;
      const authorKey = JSON.stringify(author);
      if (authorKey !== shown.author) {
        const drawn =
          author === null || identity === undefined ? null : identity(author.login, author.avatar);
        by.replaceChildren(...(drawn === null ? [] : [...separator(), drawn]));
        by.hidden = drawn === null;
        shown.author = authorKey;
      }

      if (member.readiness !== undefined) {
        const readiness = member.readiness;
        if (shown.readiness === undefined) {
          link.insertBefore(spoken, copy);
          end.insertBefore(cell, number);
        }
        const readinessKey = JSON.stringify(readiness);
        if (readinessKey !== shown.readiness) {
          spoken.textContent = readiness?.label ?? "";
          const glyph = readinessIcon(readiness, { named: false });
          cell.replaceChildren(...(glyph === null ? [] : [glyph]));
          shown.readiness = readinessKey;
        }
      }
    },
  };
}
