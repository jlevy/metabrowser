- **A lines summary leaves out a line total of zero.** A change that only adds lines
  reads “+1,234” rather than “+1,234 −0”, one that only deletes them reads “−567”, and
  one that changes no lines reads a gray “0 lines”; one that adds and deletes still
  shows both. This holds wherever Metabrowser says a change’s lines: a pull request’s row
  and a stack’s heading in the Pulls tab, a pull request’s page, the Diff summary and
  its file and folder rows, a diff’s file bars, the changed files’ summary and its rows,
  a commit’s hover card, totals line, and file list, and `metab --diff`’s text, and for
  plugins through `metabrowser.changeLine`
  ([Brief Change Line](docs/design-system.md#brief-change-line)).
