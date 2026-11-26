- A diff of more than one file has the Files tab’s **File type** menu in its toolbar,
  beside Split and Unified, on a commit’s page, a pull request’s Changes, and any other
  comparison. Choosing types narrows the diff to the changed files of those types (a
  renamed file counts under its old type and its new one), the toolbar says how many of
  the comparison’s files it keeps, with **Clear**, and the Diff summary still describes
  the whole change set.
  The menu lists the Groups, families, and extensions with the number of changed files
  of each, and `Y` opens it ([Keyboard Shortcuts](docs/keyboard-shortcuts.md)). `metab`
  answers both: a comparison route’s `types=` narrows it, and `view=types` counts its
  files by type.
