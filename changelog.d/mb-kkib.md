- **A guided review’s notes render as Markdown.** A step’s note and a group’s note
  render as the pull request’s description does, inert, in every guide, the ones already
  published included: code spans, emphasis, links, and lists render, raw HTML is cut to
  the same safe subset, and a single line break joins two lines into one paragraph.
  Titles stay plain text.
  A note whose render takes too long or fails shows as typed, with the line a
  description’s refusal says under it, and one the renderer was too busy for renders
  when the step is read again
  ([Guided Review](docs/reviewing-pull-requests.md#guided-review)). The format stays
  `Collection/v1`.

- The `guided-review` route answers each step’s rendered note as `note_html` beside
  `note`, and the rendered note of the group a step opens as `group_note_html`, each
  null when its render is refused, with the refusal’s code as `note_refusal` and
  `group_note_refusal`
  ([Collection Format](docs/project/architecture/arch-collection-format.md)).
