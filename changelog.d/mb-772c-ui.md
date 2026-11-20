- **A size line above every Diff summary.** A commit’s page, its hover card, and a pull
  request’s page say a change set’s scale on its own line, “77 commits · 83 files
  changed · 2.3 MB compressed (14.0 MB raw diff)”, its numbers bold in the line’s ink
  and the sizes’ meaning in a tooltip, and the Diff summary under it says only the
  statuses and line totals, “› 15 A, 20 D, 70 M · +1,234 −6,344”. A Pulls row ends its
  change line with what the pull request pushes.
  Plugins reach it as `metabrowser.changeSizeLine` and
  `metabrowser.changeSizeLineNodes`. See
  [Change Size Line](docs/design-system.md#change-size-line).
