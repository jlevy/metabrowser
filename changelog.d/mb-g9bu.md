- A commit’s page shows the rest of its message as Markdown, as a pull request’s page
  shows its description, through the same renderer and allowlist: lines wrapped at 72
  columns join into paragraphs, `-` and `*` lines are lists, indented and fenced code
  stays code, and an absolute link opens in a new tab
  ([Browsing History](docs/browsing-history.md)). Git’s trailers, such as
  `Signed-off-by:` and `Co-Authored-By:`, follow the text as written, one per line.
  `#123` and a bare URL stay text, as in a description, and HTML is reduced to the same
  plain markup. A body longer than a description may be
  (`GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES`), or one the renderer refuses, is shown as
  written, with a notice that says why.
  The new `GET /api/git/commit-markdown/<rev>` answers the body’s rendered `html`, its
  `trailers` as written, the `link_base` its links were resolved against, and KPress’s
  stylesheets, and `422` `body_too_large` past the bound.
