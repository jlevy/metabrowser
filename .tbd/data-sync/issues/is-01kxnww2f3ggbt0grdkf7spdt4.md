---
type: is
id: is-01kxnww2f3ggbt0grdkf7spdt4
title: Ratchet legacy browser JavaScript to noImplicitAny
kind: chore
status: open
priority: 3
version: 2
spec_path: docs/development.md
labels:
  - tooling
  - typescript
  - ratchet
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-16T16:41:32.898Z
updated_at: 2026-07-16T16:44:32.582Z
---
Migrate the remaining JavaScript compatibility allowlist into the strict TypeScript checkJs project. The 2026-07-16 baseline is 10 files, 7,124 JavaScript lines, and 532 diagnostics with noImplicitAny=true; text/index.js has already graduated. Acceptance: annotate or refactor files incrementally, move each clean file from tsconfig.legacy.json into the strict tsconfig.json surface, update the measured baseline, and remove the legacy project once empty.

## Notes

Annotated text/index.js and moved it into the strict checkJs project. Remaining allowlist measured at 10 files, 7,124 JavaScript lines, and 532 noImplicitAny diagnostics. devtools/npm_policy.py pins the exact shrinking allowlist. Full release gate passes.
