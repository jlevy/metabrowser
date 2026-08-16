# tbd Docs in This Repository

Documents that tbd serves — guidelines, shortcuts, and templates — normally live in the
gitignored `.tbd/docs/` cache.
The files here are the exception: copies kept in the repository so they are visible on
GitHub, reviewable in pull requests, and editable.
A file here shadows the tbd-provided document of the same name everywhere it was served,
so `tbd guidelines <name>` returns this copy.

Names are identity: a document is `<kind>/<name>.md`, and nested subfolders are not
scanned. Run `tbd docs status` for the current state of each file.

## Guidelines

- [electron-app-development-patterns](guidelines/electron-app-development-patterns.md) —
  building a clean, minimal, standalone Electron app: process model, backend integration
  for Node, Bun, Python, or native code, build system, security baseline, packaging,
  signing, and updates.

  Maintained here rather than tracked against the tbd-provided version, because this
  copy is a rewrite rather than a set of local edits.
  Do not run `tbd docs fork` for this name: forking would overwrite this file with the
  upstream document. The intent is to contribute this version upstream.
  Its dated companion is
  [Electron and desktop shell architectures](../project/research/research-2026-08-16-electron-desktop-architectures.md).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
