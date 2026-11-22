- **A size line above every Diff summary.** A commit’s page, its hover card, and a pull
  request’s page say a change set’s scale on its own line, “77 commits · 83 files
  changed · 2.3 MB compressed (14.0 MB raw diff)”. A tooltip explains the two sizes.
  The Diff summary below shows the statuses and line totals, “› 15 A, 20 D, 70 M ·
  +1,234 −6,344”. Plugins reach it as `metabrowser.changeSizeLine` and
  `metabrowser.changeSizeLineNodes`. See
  [Change Size Line](docs/design-system.md#change-size-line).
