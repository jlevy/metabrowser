- The text in a pull request’s description, comments, and reviews, and in a commit’s
  message, now has more room between it and its box’s left and right borders, so a
  heading that opens a description no longer sits against the border.
  Every bordered box that holds prose takes one design token,
  `--boxed-prose-padding-inline`, which `--github-pull-text-inset` and the commit
  message’s box read; a card’s head, a commit’s row, and a review comment’s hunk lines
  move in with the text, so an avatar and the text under it still start at one x
  ([Boxed Prose](docs/design-system.md#boxed-prose)).
