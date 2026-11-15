---
type: is
id: is-01m7ey9s14evcxy1bx74xy81s7
title: Pending-tally record hard-codes generation 0; directory refresh rewalks without a depth bound
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:47.779Z
updated_at: 2026-11-15T06:28:47.779Z
---
The pending-tally server record sets generation and write_generation to 0. A refresh of one directory rewalks its whole subtree with no depth bound.
