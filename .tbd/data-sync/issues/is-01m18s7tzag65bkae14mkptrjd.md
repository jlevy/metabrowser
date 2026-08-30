---
type: is
id: is-01m18s7tzag65bkae14mkptrjd
title: The file tree resolves icon and colour through the registry
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndt127q6zs53zcr5assk5d
created_at: 2026-08-30T07:30:43.818Z
updated_at: 2026-08-30T09:26:09.189Z
---
Replaces FILE_TYPES in app.js -- sixteen hand-maintained matchers resolving to nine `ft-*` classes -- with a lookup through the shipped registry table.

WHAT THE READER GETS, in the reviewer's own example: `.js` and `.mjs` and `.jsx` become one icon and one colour because they are one family, and `.json` and `.toml` stop being painted as YAML because they are three families with three hues. Today the first three differ and the last three are identical, which is precisely backwards.

WHAT DOES NOT CHANGE. `window.MetabrowserFileTypes` keeps `iconFor` and `classFor`; it is a documented SDK surface and plugins call it. The signatures stay, the resolution behind them changes, and `PLUGIN_SDK_VERSION` moves only if a caller can observe a break.

COLOUR MECHANISM. Reuse what the Overview already uses rather than inventing a second one: the `mb-distribution-mark` class plus `--mb-distribution-color-light` / `--mb-distribution-color-dark`. One family, one colour, everywhere it appears -- which is the whole point of the registry and is why the tree currently disagrees with the bars beside it.

DONE WHEN FILE_TYPES and its matcher helpers are deleted, no `ft-*` class remains in the tree path, and the fallback for an unknown extension is the generic file icon with no colour.

## Notes

Done. FILE_TYPES and its matcher helpers are gone. Classification delegates to MetabrowserFileTypeTaxonomy rather than being reimplemented -- I wrote a parallel index first and replaced it once I found the runtime, which was the same mistake this epic exists to fix. window.MetabrowserFileTypes keeps classFor and iconFor and gains styleFor and familyFor; iconFor returns style beside svg and cls, because 56 families cannot travel in class names.
