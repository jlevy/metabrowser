---
type: is
id: is-01m2kw2bht6rte4gtjdq39n1yt
title: "GitHub Phase 2C review: publish selected-branch revision-subject PR"
kind: task
status: closed
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - stack:publication
  - release:v0.12.0
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
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T01:07:30.490Z
updated_at: 2026-09-23T07:37:11.577Z
started_at: 2026-09-16T21:10:44.928Z
closed_at: 2026-09-23T07:37:11.575Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-bgs7 (URL open: HTTPS mirror, internal GitHub resolver, ref/path split, serving), with no public reducer SDK."
resolution: null
duplicate_of: null
---
Independently review selected-branch integration over the already published immutable Git-tree source. Resolve findings through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on the exact green Phase 2B provider-job/convergence publication head recorded by mb-bf94. Prove full-OID selection, bounded missing-ref fetch, concurrent revision subjects, offline and unavailable states, and no checkout, index, or worktree mutation. Record exact PR, base, head, OIDs, formal stack view, review, final green CI, and mb-n2ro registration. Do not merge.
