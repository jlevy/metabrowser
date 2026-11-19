- A pull request’s description no longer shows as raw Markdown for a second or more when
  the pull request opens before its full record is cached.
  The page opened on the description prepared ahead of selection and asked for no
  Markdown until the full record arrived; now it renders that description at once, and
  the record that follows keeps the render.
  A text whose render is still on its way past the page’s short first-paint hold shows a
  quiet placeholder in its place, never its source; source shows only when the render
  will not come, with the line that says why.
  The same holds for the comments in view when the full record arrives, which are now
  asked for before they first show, and the placeholder stops pulsing under reduced
  motion. `GET /api/plugin/github/pull-markdown` renders a pull request’s description
  from its prepared core when no record is cached, and answers `core_revision` for it.
