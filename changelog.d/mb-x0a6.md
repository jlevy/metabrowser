- **A PDF in a Markdown document stays in Metabrowser.** A link to a `.pdf` opens the
  PDF’s own page, and an embedded one, `![](report.pdf)`, `<img src="report.pdf">`, or
  `![[report.pdf]]`, shows a card with its first page, its name, and its page count, and
  a View link to its page, instead of a broken image or a link that replaced the page
  with the bare PDF. A document never starts the PDF’s viewer itself.
  A PDF named without `.pdf` embeds as any other file does.

- **Plugin SDK:** the markdown plugin now requires `pdf`, whose `mountPdfCard` draws a
  document’s embedded PDF.

- **App contract:** `metab --plugins --json` lists `pdf` among the markdown plugin’s
  `requires`, since a document draws an embedded PDF’s card with the pdf plugin.
  The macOS app reads the list as it is and needs no change.
