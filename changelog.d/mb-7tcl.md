- **A PDF’s first page in a diff.** A diff that adds, changes, or deletes a `.pdf` shows
  a card with the PDF’s first page, its name, and its page count below the binary file’s
  line, without starting a PDF viewer.
  A PDF’s own page shows the same first page behind the browser’s viewer while the
  viewer loads.

- **Previews of untrusted PDFs are drawn only in a sandbox.** Metabrowser draws the
  first page itself, with PDFium in a separate process under a deadline and resource
  limits. For an `--untrusted` folder, a GitHub repository, or a pull request, that
  process runs only inside macOS’s sandbox, which lets it open no connection, write no
  file, and read nothing of yours; on a system without one, such a PDF’s card has no
  image and says why.

- **Plugin SDK:** the `pdf` plugin exports `mountPdfCard`, for a plugin that shows a PDF
  where a viewer does not belong, and serves `/api/plugin/pdf/preview` and
  `/api/plugin/pdf/preview-image`. The diff plugin now requires `pdf`.

- **App contract:** `metab --plugins --json` lists `pdf` among the diff plugin’s
  `requires`, since a diff draws a PDF’s card with the pdf plugin.
  The macOS app reads the list as it is and needs no change.
