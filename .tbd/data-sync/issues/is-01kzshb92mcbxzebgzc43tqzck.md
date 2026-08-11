---
type: is
id: is-01kzshb92mcbxzebgzc43tqzck
title: "PR #30 review R2: preserve symlink-only folder state on live patches"
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01kzshazdfnw7wz3h768kgbfmg
created_at: 2026-08-11T23:08:29.651Z
updated_at: 2026-08-11T23:20:31.342Z
closed_at: 2026-08-11T23:20:31.341Z
close_reason: Fixed with regression coverage; make verify passes (891 pytest tests and 28 golden CLI scenarios).
---
PR #30 Cursor review thread PRRT_kwDOTX174c6YZk4I. src/metabrowser/static/app.js:4622-4628 and src/metabrowser/tree.py:666-669. Live aggregate patches can mark folders containing only symlinks as empty.

## Notes

Fixed: finalized inventory directory events now carry explicit has_children state, keeping symlink-only folders visibly non-empty without counting symlinks as files. Raw walker streaming schema remains unchanged. Added live add/remove and wire-contract regressions.
