- A rendered Markdown diff, in a pull request’s Changes and Docs, now spaces its
  headings, paragraphs, lists, quotes, and code blocks as the file’s Document view does.
  Before, an h2 sat 20 px further below a paragraph than in the document, and two
  paragraphs were 20 px further apart, because each block’s row padded it and kept its
  margins. A changed block’s fill and change gutter are now drawn around its text without
  moving it, so two changed blocks next to each other show two bands rather than one
  ([Rendered Diff Spacing](docs/design-system.md#rendered-diff-spacing)).
