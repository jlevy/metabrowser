- A changed Markdown, YAML, or JSON file in a diff always has its Rendered | Source
  chooser. A file whose rendered diff the server refused, for its size, a task list, raw
  HTML, or footnotes, lost the chooser and showed only Source with nothing to say why.
  Large documents now render, bounded by the rendering process’s deadline instead of a
  size cutoff, and a file that still cannot render keeps Rendered in place, unavailable,
  with the reason as its tooltip.
