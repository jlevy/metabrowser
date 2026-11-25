// A native stack's member as one row, the member row of docs/design-system.md, "Stacks": the
// pull request's state icon in the tree's icon slot, its title bold in text ink and cut short,
// and at the line's end, together, its place, a muted dot, and its number, "14/15 · #455", a
// Pulls row's order, the title, the place, and the number. The stack menu on a pull request's
// page draws its members with these classes (`createStackMenu` in pull-page.js), so one set of
// rules in styles.css lays out both; the stack's own page draws its members through this
// builder (stack-page.js). A member whose state is not known yet keeps the icon's slot, empty,
// so every member's title starts at one edge.

import { pullStateIcon } from "./pull-state.js";

/**
 * @typedef {{
 *   number: number,
 *   place: string,
 *   title: string | null,
 *   state: import("./pull-state.js").PullState | null,
 * }} StackMemberLine
 */

/**
 * The words a member row shows for its title: the member's own, or "Pull request #N" for one
 * not read yet, as the stack menu says it.
 *
 * @param {StackMemberLine} member
 */
export function memberTitle(member) {
  return member.title || `Pull request #${member.number}`;
}

/**
 * Fill *row*, the member's link, with its line: the state icon, then the title, and at the
 * line's end the place, a muted dot, and the number. The whole title is the row's tip, which
 * the shell shows only while the line cuts it short.
 *
 * @param {HTMLElement} row
 * @param {StackMemberLine} member
 * @param {(title: string) => Array<Node | string>} titleNodes The SDK's `titleNodes`.
 */
export function fillStackMemberRow(row, member, titleNodes) {
  const make = (/** @type {string} */ tag, /** @type {string} */ className) => {
    const element = document.createElement(tag);
    element.className = className;
    return element;
  };
  const title = memberTitle(member);
  row.classList.add("github-pull-stack-member");
  row.setAttribute("data-tip-text", title);
  /** @type {HTMLElement} */
  let icon;
  if (member.state === null) {
    icon = make("span", "github-pull-state-icon");
    icon.setAttribute("aria-hidden", "true");
  } else {
    icon = pullStateIcon(member.state);
  }
  const text = make("span", "github-pull-stack-member-title");
  text.append(...titleNodes(title));
  const position = make("strong", "github-pull-stack-member-position");
  position.textContent = member.place;
  const dot = make("span", "github-pull-stack-dot");
  dot.setAttribute("aria-hidden", "true");
  dot.textContent = "·";
  const number = make("span", "github-pull-stack-member-number");
  number.textContent = `#${member.number}`;
  const copy = make("span", "github-pull-stack-member-copy");
  copy.append(text, " ", position, " ", dot, " ", number);
  row.replaceChildren(icon, copy);
  return row;
}
