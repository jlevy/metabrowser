---
type: is
id: is-01m18s7vz7sxjemx03328vmm70
title: Pin the taxonomy at the boundary a reader sees
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndt127q6zs53zcr5assk5d
created_at: 2026-08-30T07:30:44.838Z
updated_at: 2026-08-30T09:26:09.442Z
---
The defect this epic fixes is invisible to every test in the repository, because both taxonomies are internally consistent -- they simply disagree with each other. A test that asks either one what it thinks passes.

So pin the RELATION, in tests/dom against rendered rows:

- `.js`, `.mjs`, `.cjs`, `.jsx` render one icon and one colour. Today `.mjs`, `.cjs` and `.jsx` are not in FILE_TYPES at all and fall through to the generic file icon with no colour, so this fails before the change.
- `.json`, `.toml`, `.yaml` render three DIFFERENT colours. Today all three are `ft-yaml`.
- `.py` and `.ts` render different colours. Today both are `ft-code`.
- A row's colour equals the colour the Overview gives that family, which is the invariant the whole epic exists to restore.
- An extension the registry does not know renders the generic icon and no colour.

DONE WHEN these fail against the current build for the stated reasons and pass after.

## Notes

Done, and falsified before being trusted: run against the table it replaces, the new test fails on all three counts -- .js/.mjs/.cjs/.jsx gave 2 icons with 3 of 4 uncoloured, json/toml/yaml gave 1 colour instead of 3, python and typescript were identical. Also pins that a row's colour is the family's declared distribution colour, which is the invariant the epic exists to restore.
