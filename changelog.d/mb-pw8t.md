- A Pulls row now reads as one run that wraps, each line starting under the title: the
  title, a stack member’s place, the number, and the lines the pull request adds and
  deletes with the chevron after them, such as “Fix the reader · 1/6 · #455 · +1,234
  −567 ›”, and the author and the age on the line below.
  The title is no longer cut short at two lines, so at the tab’s default width most rows
  take a line more than before.
  Only the lines and the chevron open and close the row’s files; a click anywhere else
  opens the pull request ([The Pulls Tab](docs/design-system.md#the-pulls-tab)).

- A pull request’s stack menu shows each member’s place before its number, “1/6 · #455”,
  both at the end of its line, the order a Pulls row has them
  ([Stacks](docs/design-system.md#stacks)).

- Returning to the Pulls tab keeps the pull request you opened in view when its stack
  was read while you were on another tab, wherever its rows are taller or shorter than
  the list first placed them.
