// A native stack's member as one row, the member row of docs/design-system.md, "Stacks": the
// pull request's state icon in the tree's icon slot, its title bold in text ink and cut short,
// and at the line's end, together, its place, a muted dot, its number, and another dot and its
// author, the shell's actor identity, "14/15 · #455 · jlevy", a Pulls row's order, the title,
// the place, the number, and the author (docs/design-system.md, "Authors Follow Pull
// Requests"). The stack menu on a pull request's page (`createStackMenu` in pull-page.js), the
// stack's own page (stack-page.js), and a guide's pull request row (`pullRow` in
// guided-review.js) all draw their rows with `stackMemberRow`, so the rows are one row by
// construction, and one set of rules in styles.css lays them out. A guide's pull request may
// be in no stack, and then its row has no place and keeps the rest in order. A member whose
// state is not known yet keeps the icon's slot, empty, so every member's title starts at one
// edge.

import { pullStateIcon } from "./pull-state.js";

/**
 * @typedef {{
 *   number: number,
 *   place: string | null,
 *   placeTip?: string,
 *   title: string | null,
 *   state: import("./pull-state.js").PullState | null,
 *   author: {login: string, avatar: string | null} | null,
 * }} StackMemberLine `place` is null for a guide's pull request in no stack, and
 *   `placeTip` names the place's stack where nothing around the row does, as on a guide's
 *   row: "Stack #71, position 1 of 3".
 */

/**
 * A member row drawn into its link, and `show`, which draws a member's line into it.
 *
 * @typedef {{link: HTMLElement, show(member: StackMemberLine): void}} StackMemberRow
 */

/**
 * Make *link* a member's row: the state icon, then the title, and at the line's end the
 * place, a muted dot, the number, and another dot and the author, which *identity* draws; a
 * line with no place starts its end at the number, and a member whose author is not known, or
 * a row with no *identity*, has neither the second dot nor the author, not even the space
 * before them. `show` changes only what differs from the
 * line the row shows, so a row drawn again keeps its nodes, and its author's avatar its
 * image. The whole title is the row's tip, which the shell shows only while the line cuts it
 * short (docs/design-system.md, "Tooltips Add Information"); a member not read yet is titled
 * "Pull request #N".
 *
 * @param {HTMLElement} link
 * @param {(title: string) => Array<Node | string>} titleNodes The SDK's `titleNodes`.
 * @param {(login: string, avatar: string | null) => HTMLElement} [identity] The author's
 *   identity, `authorLabel` in pull-page.js.
 * @returns {StackMemberRow}
 */
export function stackMemberRow(link, titleNodes, identity) {
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
  const emptyIcon = () => {
    const element = make("span", "github-pull-state-icon");
    element.setAttribute("aria-hidden", "true");
    return element;
  };
  link.classList.add("github-pull-stack-member");
  const title = make("span", "github-pull-stack-member-title");
  const position = make("strong", "github-pull-stack-member-position");
  const placeDot = dot();
  const number = make("span", "github-pull-stack-member-number");
  const by = make("span", "github-pull-stack-member-by");
  by.hidden = true;
  const copy = make("span", "github-pull-stack-member-copy");
  copy.append(title, " ", position, " ", placeDot, " ", number, by);
  link.replaceChildren(emptyIcon(), copy);
  /** @type {{words: string | null, state: StackMemberLine["state"] | undefined, author: string | null, placed: boolean}} */
  const shown = { words: null, state: undefined, author: null, placed: true };
  return {
    link,
    show(member) {
      const words = member.title || `Pull request #${member.number}`;
      if (shown.words !== words) {
        title.replaceChildren(...titleNodes(words));
        link.setAttribute("data-tip-text", words);
        shown.words = words;
      }
      const placed = member.place !== null;
      if (shown.placed !== placed) {
        copy.replaceChildren(
          title,
          ...(placed ? [" ", position, " ", placeDot] : []),
          " ",
          number,
          by,
        );
        shown.placed = placed;
      }
      const place = member.place ?? "";
      if (position.textContent !== place) {
        position.textContent = place;
      }
      const placeTip = member.placeTip ?? null;
      if (position.getAttribute("data-tip-text") !== placeTip) {
        if (placeTip === null) {
          position.removeAttribute("data-tip-text");
        } else {
          position.setAttribute("data-tip-text", placeTip);
        }
      }
      const numbered = `#${member.number}`;
      if (number.textContent !== numbered) {
        number.textContent = numbered;
      }
      if (shown.state !== member.state) {
        // Named, as a Pulls row's icon is, since nothing else on the line says the state.
        link.replaceChildren(
          member.state === null ? emptyIcon() : pullStateIcon(member.state),
          copy,
        );
        shown.state = member.state;
      }
      const author = identity === undefined ? null : member.author;
      const said = author === null ? "" : `${author.login}\n${author.avatar ?? ""}`;
      if (shown.author !== said) {
        by.replaceChildren(
          ...(author === null || identity === undefined
            ? []
            : [" ", dot(), " ", identity(author.login, author.avatar)]),
        );
        by.hidden = author === null;
        shown.author = said;
      }
    },
  };
}
