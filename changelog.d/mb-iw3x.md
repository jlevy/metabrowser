- A diff’s toolbar now offers **Diff** | **Current** beside **Split** | **Unified**:
  **Diff** is the diff as before, and **Current** shows the new version alone, with its
  changes marked and nothing removed.
  In **Source**, Current draws the new file’s lines in one column, added lines marked,
  whatever the layout; in **Rendered**, a Markdown file’s added blocks and front matter
  keys stay marked and its removed ones are left out, and a YAML or JSON tree is drawn
  without its removed entries.
  A deleted file, and a file the change left empty, say so.
  It is one choice for the whole diff, on a pull request’s Changes and Docs, a commit’s
  page, and a patch. Changes, a commit’s page, and a patch open on **Diff** and remember
  the choice as the `diff.show` preference; a pull request’s Docs tab, which has a
  toolbar again to hold it, opens on **Current** and remembers its own choice as
  `github.docs.show`, so neither moves the other.
  `N` switches between the two
  ([Comparison view](docs/reviewing-pull-requests.md#comparison-view)), and the line or
  block you are reading stays where it was on the screen.
  While Current is shown, the layout control stays in place with its choices
  unavailable. In a narrow pane the two choosers move to the toolbar’s next line
  together, still at its right.
