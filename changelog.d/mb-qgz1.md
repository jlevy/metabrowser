- **A guided-review step shows a document it cites whole as Docs does.** A step
  reference that names a Markdown, YAML, or JSON file by its path alone now draws that
  file rendered, as the pull request’s Docs tab draws it, with its Rendered and Source
  choice and Diff and Current, instead of its source diff.
  A line range, and a whole file of any other format, still shows the diff’s rows
  ([Guided Review](docs/reviewing-pull-requests.md#guided-review)).

- **Plugin SDK:** the diff plugin exports `loadRenderedFile`, which draws one file of a
  comparison as the diff view does, rendered layer included
  ([Declared Dependencies](docs/plugins.md#declared-dependencies)).
