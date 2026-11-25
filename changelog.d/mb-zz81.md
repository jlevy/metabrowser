- **A diff’s `@@` separators open to the lines between its hunks.** In a pull request’s
  Changes and Docs, and on a commit’s page, each hunk’s separator in a code file is the
  diff’s fold bar, the one a long run of changed lines folds behind, with the separator
  kept beside its label: it opens to the unchanged lines above the hunk, back to the
  hunk before or the file’s start, and a bar after the last hunk opens to the rest of
  the file. A long run opens a part at a time, nearest the hunk first; the lines are
  highlighted as the hunks are, stay open across Split, Unified, and Current, and
  opening one above what you are reading leaves it where it is.
  A file whose lines cannot be read, such as a binary file or one Git converts for its
  diff, keeps its plain separators and says so
  ([Fold Expanders](docs/design-system.md#fold-expanders)).

- **Route:** `GET /api/plugin/diff/comparison`, and a pull request’s
  `/api/plugin/github/pull-comparison`, answer `view=lines&file=PATH&start=N&count=M`,
  or `end=N` for the lines before line N: up to `DIFF_GAP_LINES` lines of that change’s
  new side from its snapshot, fewer where its lines are long, with the side’s
  `line_count` and `ends_with_newline`, or a `409` whose `code` is `no_side`,
  `not_text`, `textconv`, `blob_too_large`, or `no_content`
  ([Context Between Hunks](docs/project/architecture/arch-diff-pipeline.md#context-between-hunks)).
