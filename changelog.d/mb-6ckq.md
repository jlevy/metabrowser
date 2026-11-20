- File Overview’s legend names up to nine file-type families, up from five, each at
  least 1% of the folder, then Other for the rest.
  A family at exactly 1% is named, and Details, which folds rows below that share into
  “N more”, now shows its row too.
  The rollup’s `file_type_legend` carries the new `limit`.
- File Overview’s bars start further left, at one place in every row of the Files,
  Ignored, and Total bars and of Details, with Files or Bytes and with Details open or
  closed: a label column as wide as the longest label there, the Documentation heading
  and the No extension and Markdown rows, where it had been a quarter of the table, so
  the bars start 54 px further left in the default pane.
  A longer label wraps inside the column and moves no bar, and in a pane too narrow for
  the column the bars start where they did.
  See [Aggregate Distributions](docs/design-system.md#aggregate-distributions).
