---
type: is
id: is-01m2h7gjc36fqv8cv38qd9zynr
title: "Repository library Phase 2B: open any selected branch as a revision subject"
kind: feature
status: open
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2kw2bht6rte4gtjdq39n1yt
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-15T00:29:47.265Z
updated_at: 2026-09-16T21:52:17.365Z
started_at: 2026-09-16T21:10:44.845Z
---
Integrate the immutable Git-tree source into repository URL opening. selection.py resolves slash-containing ref/path candidates locally and returns a typed missing-ref request; mb-jlon alone performs bounded network fetch. Pin the result to a full OID and serve a leased GitRevisionSubject through the content-source lifecycle without switching or materializing a checkout. Cover default, non-default, slash branches, tags, offline/unavailable refs, two concurrent subjects, object leases, reclamation, and cli-github-branch-open.
