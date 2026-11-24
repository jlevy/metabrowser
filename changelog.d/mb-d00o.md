- **A text file named `.pdf` opens as text.** The `pdf` plugin claims a `.pdf` only when
  its bytes start with `%PDF-`, so a misnamed text file shows its source instead of a
  viewer that cannot open it.
  An all-ASCII PDF is still a PDF.

- **Plugin manifests:** a `magic` rule with `ext` or `exts` beside it now also claims a
  file with one of those extensions that reads as text, when its leading bytes hold the
  magic ([Plugins](docs/plugins.md)).
