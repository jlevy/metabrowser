- **A stack’s pull requests sit beside its Whole stack row again, one level in.** Under
  a stack’s row in the Pulls tab the Whole stack row comes first and each pull request
  follows it at the same level; none is nested under Whole stack, and nothing on that
  row hides them. The stack’s row keeps its size and age, “Stack #286 · 4 pulls”
  ([Stack Groups in the Pulls Tab](docs/design-system.md#stack-groups-in-the-pulls-tab)).

- **Whole stack expands the whole stack’s changed files.** The row reads “Whole stack ·
  +1,234 −567” with a chevron after the lines, as a pull request’s row ends, and no
  chevron before it. A press on the lines or the chevron lists every file the stack
  changes under the row, the files the stack’s page shows in its Diff summary, and a
  press anywhere else still opens the stack’s page.
  Space, Right, and Left on the row open and close the files as they do a pull
  request’s; Enter opens the page.
  The files are read when first opened.
