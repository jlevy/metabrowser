- A short commit ID is seven characters everywhere, as GitHub shows them, and on the
  page always in the commit-ID face and the same gray: the branch chooser’s button and
  rows, the page heading, the Commits tab, the freshness offer, and the pull request
  page, its timeline’s commit links included.
  The CLI’s messages, `metab --version`, and the macOS app’s About box cut an ID to the
  same seven. See [Short Commit IDs](docs/design-system.md#short-commit-ids).
  The JSON routes still carry full IDs, and the history routes’ `short_id` is still
  Git’s own abbreviation.

- The plugin SDK has `metabrowser.shortCommit(commit)`, which cuts a commit ID to the
  length the page shows.

- The macOS app records the full commit it was built from (`MetabrowserSourceCommit`),
  and a release check compares it whole with the tag’s commit rather than as a prefix.

- **App contract:** The macOS app copies `SHORT_COMMIT_CHARS` from
  `src/metabrowser/commit_ids.py` as `AppIdentity.shortCommitChars`, the length its
  About box shows of the build’s commit; `tests/golden/app-contract-copies.txt` records
  it.
