- A task list in Rendered, and in the Document view of an untrusted document, draws its
  boxes, each ticked as the document ticks it, where it drew none before, so ticking or
  unticking a box is a change that **Rendered** shows.
  A checkbox written in raw HTML, such as one in a table cell, draws and changes the
  same way, and a tick beside a word edit in the same item still marks the words.

- Raw HTML that writes an attribute twice, or writes words where the render reads no
  value, such as in a checkbox’s `checked` or a link’s `target`, is a change only
  **Source** shows, so its block is never folded away and the rendered diff reports it
  `source_only`.
