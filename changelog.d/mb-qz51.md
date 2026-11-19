- Markdown documents now draw fenced `mermaid` blocks as diagrams, as GitHub does, with
  the same Mermaid release GitHub uses, in the page’s light or dark theme.
  Hovering a diagram shows buttons to copy its source, show the source in its place, and
  open it in a dialog that zooms and pans with buttons, keys, the wheel, a pinch, or a
  drag. A diagram Mermaid cannot parse shows the parse error above its source.
  Mermaid loads only for a document that has a diagram, and its `click` callbacks never
  run. With active content off, diagrams are drawn as pictures, and a label keeps its
  bold and line breaks but drops any image or link.
  `.mmd` and `.mermaid` files open as one diagram, with a Diagram view and a Source
  view. See [Browsing Files](docs/browsing-files.md#markdown).

- A pull request’s description and comments draw their `mermaid` blocks as pictures too,
  as GitHub draws them there, when Metabrowser serves a repository or pull-request URL.
  Beside a checkout, whose page may run without the untrusted page’s protections, they
  still show the block’s source.

- A fenced `svg` block in Markdown now shows as code, as GitHub shows it, where it was
  drawn as an image.

- For plugin authors: `metabrowser.ensureModule(name)` imports a published ES module
  bundle once and resolves to its namespace, beside `ensureAsset` for script bundles.
  The inert render now keeps `lang="mermaid"` on a `pre`, and no other `lang` value.
  `metabrowser.builtins.markdown.drawDiagrams(root, {inert})` draws the diagrams of a
  KPress render another plugin placed, as images unless `inert: false`.
