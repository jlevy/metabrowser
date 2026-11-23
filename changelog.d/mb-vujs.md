- Hiding the navigation pane centers a rendered document, with its table of contents,
  and a folder’s Overview in the wider page, instead of leaving them at the left edge
  with the window’s spare width beside them.
  The title, the Up button, and the tabs move with the text, and what is at the right,
  such as View on GitHub, stays there; the text glides to its place as the page slides.
  Source files, tables, diffs, and logs keep the page’s full width, and a page too
  narrow to dock a table of contents is unchanged.
  For plugin authors, a view whose body is a reading column can opt in by setting
  `--reading-unit` on the main view’s children.
  See [Hiding the Navigation Pane](docs/design-system.md#hiding-the-navigation-pane).
