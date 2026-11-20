- **Controls, badges, and messages follow one design system throughout**: every
  focusable control draws the same inset focus ring; status text (added and deleted line
  counts, failures, badges) reads at full contrast in both themes; run and agent badges
  have dark-theme colors; failures and partial results in folder Overview, the Treemap,
  diffs, and embedded notes are notice boxes with a severity; Retry buttons, the
  structured view’s copy button, and the text fields in the menu and ref selector use
  the shared primitives; counts follow your locale everywhere; and the GitHub plugin
  says a rate limit, a failed load, or a refused refresh in one wording, without HTTP
  status codes. See [Design System](docs/design-system.md).

- **Plugin authors**: new shared tokens `--focus-ring-width`, `--focus-ring-color`,
  `--focus-ring-offset`, `--status-*-text`, `--badge-*-bg` and `--badge-*-text`, and
  `--diff-add-row-bg` / `--diff-del-row-bg`, and a `.field` primitive for text fields
  ([Design System](docs/design-system.md)).
