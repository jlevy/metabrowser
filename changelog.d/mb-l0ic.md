- Mermaid diagrams in a pull request’s description and comments are now drawn beside a
  checkout too, not only on a repository URL’s page.
  They are laid out in a hidden frame that can load nothing, so a diagram that names an
  image cannot fetch it; one drawn around an image, Mermaid’s image shape, shows its
  source with a message that its image is not loaded
  ([Trust](docs/reviewing-pull-requests.md#trust)).

- Plugin SDK: `metabrowser.moduleUrl(name)` returns an on-demand module bundle’s
  absolute URL, for a frame that imports it in its own realm, and the Markdown plugin’s
  `drawDiagrams(root, {isolated: true})` lays untrusted diagrams out in that frame
  ([Browser SDK](docs/plugins.md#browser-sdk)).
