---
type: is
id: is-01m7wyjyxgdmtdze2vt8eb7ter
title: Map merged pull requests and stacks to Linear issues through a linear label
kind: feature
status: open
priority: 2
version: 1
labels:
  - linear
dependencies: []
created_at: 2026-11-20T17:03:10.767Z
updated_at: 2026-11-20T17:03:10.767Z
---
The Linear board shows the work that merges: one issue per native GitHub stack, one per standalone pull request's bead, nested under the epic or feature it belongs to. tbd selects by the linear label (open or closed) instead of every open bead (576 issues on 2026-11-20). Backfill covers PRs merged 2026-11-17 to 2026-11-20 (138 PRs, 113 units, 12 parents); nine retroactive beads cover PRs that named none and stack #505. The convention is in docs/development.md#linear. tbd gaps found: --push does not send descriptions; the managed block's PRs line is never fed from refs; create --from-file rejects a titled file.
