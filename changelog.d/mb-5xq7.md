- Markdown lays itself out with the HTML attributes github.com keeps, as github.com
  does: `align` on a paragraph, `div`, heading, image, or table cell or row, and `width`
  and `height` on an image or a table cell.
  Metabrowser’s own README, a 192-pixel logo in a `<p align="center">` over a centered
  title, drew its logo at the file’s 512 pixels against the left edge with active
  content off (a repository URL, a served mirror, or `--untrusted`), whose allowlist
  dropped both attributes.
  In every render an image sized by its `height` alone now takes that height, an image
  floated by `align` keeps github.com’s room beside it and stays inside the document, an
  image sized or aligned by these attributes has no margin, so a badge sits on its line
  of text, and a table cell’s or row’s `align` sets the cell’s text.
  An `<img>` with both a `width` and a `height` now draws at exactly that size, as on
  github.com, even where a narrow pane caps its width and its height stays; before, it
  kept its file’s proportions.
  A wiki embed sized as `![[image.png|640x480]]` keeps its file’s proportions, as
  before. See [Markdown](docs/browsing-files.md#markdown).
