---
type: is
id: is-01m2kw2bht6rte4gtjdq39n1yt
title: "GitHub Phase 2B review: publish selected-branch revision-subject PR"
kind: task
status: in_progress
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
  - type: blocks
    target: is-01kxry31k2e62styhj8t59jj12
  - type: blocks
    target: is-01m2h5an32kbkp6zfkhkjzq55f
  - type: blocks
    target: is-01m2h9jka5t3kw909ae7xefx8d
  - type: blocks
    target: is-01m2kvemzp183vrykz849c0s5a
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T01:07:30.490Z
updated_at: 2026-09-16T21:12:09.467Z
started_at: 2026-09-16T21:10:44.928Z
---
Independently review selected-branch integration over the already published immutable Git-tree source. Resolve findings through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on the exact green repository URL-open head. Prove full-OID selection, bounded missing-ref fetch, concurrent revision subjects, offline and unavailable states, and no checkout, index, or worktree mutation. Record exact PR, base, head, OIDs, formal stack view, review, final green CI, and mb-n2ro registration. Do not merge.
