- **A guided review’s file diffs fold.** In a pull request’s or a stack’s Guided Review,
  each file a step shows a diff of has the chevron a file has in Changes: press its bar,
  or Enter or Space on its name, to fold the diff away and open it again.
  Files start open, and a step shown again starts open
  ([Diff File Bar](docs/design-system.md#diff-file-bar)).

- **Plugin authors:** the handle the diff plugin’s `mountFilePatch` returns has
  `disclose(section, folded)`, which makes the bar and chevron that fold a file’s card
  in Changes, for a page that draws its own card around the patch; it does not depend on
  the patch ([Declared Dependencies](docs/plugins.md#declared-dependencies)).
