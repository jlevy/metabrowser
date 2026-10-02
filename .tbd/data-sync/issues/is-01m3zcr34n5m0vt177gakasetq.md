---
type: is
id: is-01m3zcr34n5m0vt177gakasetq
title: /view/.hidden/ shows 'Could not load file types.' and a skeleton that never finishes
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-02T22:46:20.564Z
updated_at: 2026-10-02T22:46:20.564Z
---
Found by the browser differential; identical on 0.11.0 and the stack, so not a landing regression. Opening a dot-folder view leaves the overview skeleton unfinished with the error text. Decide whether a hidden folder is viewable and make the view either render or say why not.
