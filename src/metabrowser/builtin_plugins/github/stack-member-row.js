// A native stack's member as one row, the member row of docs/design-system.md, "Stacks": the
// pull request's state icon in the tree's icon slot, its title bold in text ink and cut short,
// and at the line's end, together, its place, a muted dot, its number, and another dot and its
// author, the shell's actor identity, "14/15 · #455 · jlevy", a Pulls row's order, the title,
// the place, the number, and the author. The stack menu on a pull request's
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
 *   author: {login: string, avatar: string | null} | null,
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
 * line's end the place, a muted dot, the number, and another dot and the author, which
 * *identity* draws, as the stack menu draws it; a member whose author is not known has
 * neither the dot nor the author. The whole title is the row's tip, which the shell shows
 * only while the line cuts it short.
 *
 * @param {HTMLElement} row
 * @param {StackMemberLine} member
 * @param {(title: string) => Array<Node | string>} titleNodes The SDK's `titleNodes`.
 * @param {(login: string, avatar: string | null) => HTMLElement} identity
 */
export function fillStackMemberRow(row, member, titleNodes, identity) {
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
  const by = make("span", "github-pull-stack-member-by");
  if (member.author === null) {
    by.hidden = true;
  } else {
    const before = make("span", "github-pull-stack-dot");
    before.setAttribute("aria-hidden", "true");
    before.textContent = "·";
    by.append(" ", before, " ", identity(member.author.login, member.author.avatar));
  }
  const copy = make("span", "github-pull-stack-member-copy");
  copy.append(text, " ", position, " ", dot, " ", number, by);
  row.replaceChildren(icon, copy);
  return row;
}
