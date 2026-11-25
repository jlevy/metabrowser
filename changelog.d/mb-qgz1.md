- **A guided-review step shows a document it cites whole rendered.** A step reference
  that names a Markdown file by its path alone now draws that file as the pull request’s
  Docs tab draws it, and a YAML or JSON file as Changes draws it: rendered, with its
  Rendered and Source choice and Diff and Current, instead of its source diff.
  Such a file no longer counts against the step’s budget for whole files, so a large
  document shows in its step.
  A line range, and a whole file of any other format, still shows the diff’s rows
  ([Guided Review](docs/reviewing-pull-requests.md#guided-review)).

- **Guided-review route:** each reference answers `rendered`, the format the page draws
  a whole file in (`markdown`, `yaml`, or `json`), or null; a reference with a format
  carries no hunks.

- **Plugin SDK:** the diff plugin exports `mountRenderedFile`, which draws one file of a
  comparison as the diff view does, rendered layer included
  ([Declared Dependencies](docs/plugins.md#declared-dependencies)).
