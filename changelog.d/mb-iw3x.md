- A diff’s file bars now offer **Diff** | **Current** beside **Rendered** | **Source**:
  **Diff** is the diff as before, and **Current** shows the new version alone, with its
  changes marked and nothing removed.
  In **Source**, Current draws the new file’s lines in one column, added lines marked,
  whatever the layout; in **Rendered**, a Markdown file’s added blocks and front matter
  keys stay marked and its removed ones are left out, and a YAML or JSON tree is drawn
  without its removed entries.
  It is one choice for the whole diff, on every file with a text diff on a pull
  request’s Changes and Docs, a commit’s page, and a patch, and Metabrowser remembers it
  (the `diff.show` preference).
  `N` switches between the two
  ([Diff or Current](docs/reviewing-pull-requests.md#diff-or-current)). While Current is
  shown, the layout control stays in place with its choices unavailable.
