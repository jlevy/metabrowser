- **A native stack’s page is a pull request’s page for the whole stack.** Its header has
  a pull request’s parts in a pull request’s order: the Layers glyph, “Stack”, and the
  number; View on GitHub in the corner; the members, top first, each as the stack menu
  lists it, its place, number, and author at the line’s end; the top member’s head
  branch → the stack’s base; the status line; the files changed; and the Diff summary,
  closed until you open it.
  Its tabs are a pull request’s Guided Review, when the stack has a guide, Docs, and
  Changes, which is the front page without a guide
  ([The Stack Page](docs/design-system.md#the-stack-page)).

- **The Pulls tab lists a stack’s page under its members.** Each open stack’s last row,
  **Whole stack**, with the stack’s Layers glyph, opens the stack’s page, as the stack
  menu’s first row does, and is the current row while that page is open.
  J and K stop on it and open the page, Enter and Space open it, and Left goes to the
  stack’s row
  ([Stack Groups in the Pulls Tab](docs/design-system.md#stack-groups-in-the-pulls-tab)).

- **View on GitHub on a stack’s page opens the stack.** The page, each of its tabs, and
  each file of its Changes open GitHub’s page of the whole stack, `stack/<n>`, through
  the shared View on GitHub button, where a link in the page’s summary line opened the
  top member’s pull request
  ([Where It Appears](docs/design-system.md#where-it-appears)).

- **A stack’s page no longer moves while it loads.** Every row of its header is decided
  at first paint, so the stack’s answer lands moving nothing under the title, and Docs
  and Changes show their first screen in one step, as a pull request’s do.
  On a pull request’s page and a stack’s, the loading block under a diff that is still
  being laid out stays where it first shows instead of dropping as the diff grows.
