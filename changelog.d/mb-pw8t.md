- A Pulls row now reads as one run that wraps, each line starting under the title: the
  title, a stack member’s place, the number, the author, and the age, such as “Fix the
  reader · 1/6 · #455 · jlevy · 3d”, and on the line below, the lines the pull request
  adds and deletes with the chevron after them, such as “+1,234 −567 ›”. The title is
  never cut short, so at the tab’s default width most rows take four lines, and in a
  wider tab most take three.
  Only the lines and the chevron open and close the row’s files; a click anywhere else
  opens the pull request ([The Pulls Tab](docs/design-system.md#the-pulls-tab)).

- Returning to the Pulls tab keeps the pull request you opened in view when its stack
  was read while you were on another tab, wherever its rows are taller or shorter than
  the list first placed them.
