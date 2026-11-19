- A repository opened by its URL is headed by its name alone in the navigation column:
  the branch and the short commit no longer follow it there.
  The branch and tag selector under the heading names the branch, and the heading’s
  tooltip names the full commit.
  A revision of a local checkout still shows its branch and short commit beside the
  folder’s name, which its working tree’s page shares.

- A short commit ID is the size of the text around it wherever it appears, in a commit’s
  page and hover card, the branch and tag selector, the freshness row, and a pull
  request’s timeline. Its monospace face is scaled to the x-height of the interface sans
  in each font set, where it read larger than the text beside it in some places and
  smaller in others ([Short Commit IDs](docs/design-system.md#short-commit-ids)).
