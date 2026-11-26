- **A stack’s page has a pull request’s header for the whole stack.** Under the title, a
  badge for each state its pull requests are in, such as **2 Pulls Open**, then when one
  was last opened and last updated; their authors and the commits they want to merge,
  with when the stalest was fetched; the branches; every pull request’s labels, each
  once; and the commits, files, and size of the stack’s change.
  The pull requests themselves now sit under a **2 Pulls** toggle just above the Diff
  summary, closed at first as the Diff summary is
  ([The Stack Page](docs/design-system.md#the-stack-page)).
  `GET /api/plugin/github/stack` answers `states`, `opened_at`, `updated_at`, `authors`,
  `mergers`, `fetched_at`, `labels`, `commits`, and `size` for them, the size its
  combined comparison’s own; `GET /api/plugin/github/stacks` answers each member’s
  `labels`, from which the page decides its labels row at first paint.

- In the Pulls tab a stack’s row no longer has a stack icon: its label starts where its
  pull requests’ icons do, and its **Whole stack** row, in the Pulls tab and the stack
  menu, carries the icon in the text’s ink ([Stacks](docs/design-system.md#stacks)).
