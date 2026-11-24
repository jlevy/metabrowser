- A Markdown file in a diff with raw HTML, a task list, footnotes, or a private-use
  character such as U+E000 renders in Rendered, where it showed only Source before.
  Raw HTML, such as a centered logo, a `<details>`, or a `<br>`, renders as the Document
  view renders it, and an HTML edit it does not show, such as a class or a style, is a
  change that **Source** shows.
  A `<details>` in a changed block shows open, so the words marked inside it show.
  A task list renders without its boxes, as the Document view of an untrusted document
  shows it, so ticking or unticking a box is a change that **Source** shows.
  A footnote’s reference shows its number in place, and its note shows where its
  definition is written, numbered as the Document view numbers it, except where a
  reference written inside math, which Rendered shows as source text, comes first.
