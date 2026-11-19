- Markdown documents now draw fenced `mermaid` blocks as diagrams, as GitHub does, with
  the same Mermaid release GitHub uses, in the page’s light or dark theme.
  Hovering a diagram shows buttons to copy its source, show the source in its place, and
  open it in a dialog that zooms and pans with buttons, keys, the wheel, a pinch, or a
  drag. A diagram Mermaid cannot parse shows the parse error above its source.
  Mermaid loads only for a document that has a diagram, and its `click` callbacks never
  run. With active content off, diagrams are drawn as pictures.
  `.mmd` and `.mermaid` files open as one diagram, with a Diagram view and a Source
  view. See [Browsing Files](docs/browsing-files.md#markdown).

- A fenced `svg` block in Markdown now shows as code, as GitHub shows it, where it was
  drawn as an image.

- For plugin authors: `metabrowser.ensureModule(name)` imports a published ES module
  bundle once and resolves to its namespace, beside `ensureAsset` for script bundles.
  The inert render now keeps `lang="mermaid"` on a `pre`, and no other `lang` value.
