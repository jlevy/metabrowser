---
type: is
id: is-01kxnww2f3ggbt0grdkf7spdt4
title: Ratchet legacy browser JavaScript to noImplicitAny
kind: chore
status: open
priority: 3
version: 7
spec_path: TODO.md
labels:
  - tooling
  - typescript
  - ratchet
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:41:32.898Z
updated_at: 2026-11-14T18:44:42.653Z
extensions:
  linear:
    id: 5169c336-d301-4100-9653-ce96dd092cec
    linked_at: 2026-08-16T08:05:54.238Z
---
Migrate the modules in tsconfig.legacy.json's files array into the strict tsconfig.json project. That array is the allowlist (docs/development.md); `npx --no-install tsc --noEmit -p tsconfig.legacy.json --noImplicitAny` lists the diagnostics that remain. Annotate or refactor one file at a time, move each clean file out of the legacy project, and delete tsconfig.legacy.json and its Makefile and devtools/lint.py entries once the array is empty.

## Notes

Annotated text/index.js and moved it into the strict checkJs project. Remaining allowlist measured at 10 files, 7,124 JavaScript lines, and 532 noImplicitAny diagnostics. devtools/npm_policy.py pins the exact shrinking allowlist. Full release gate passes.
