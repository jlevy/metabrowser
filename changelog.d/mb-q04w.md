- **Rendered documents print in KPress’s print model.** A Markdown document, or a
  folder’s README, prints as KPress’s own PDF export draws it, in the browser and in the
  macOS app alike: the print button waits for the document’s images, KPress’s print
  faces, and its diagrams before it prints; the page prints on light paper whatever the
  app’s theme; a README’s centred logo stays centred; and the Overview prints the README
  alone, without its label.
  In the app, whose WebKit printed lazily loaded images as nothing, left headings alone
  at a page’s foot, and printed edge to edge, pages now have KPress’s margin, headings
  stay with what follows them, and every image prints.
  See [Print](docs/design-system.md#print).
