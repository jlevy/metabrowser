---
type: is
id: is-01m2h7gjc36fqv8cv38qd9zynr
title: "Repository library Phase 2C: open any selected branch as a revision subject"
kind: feature
status: closed
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2kw2bht6rte4gtjdq39n1yt
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-15T00:29:47.265Z
updated_at: 2026-09-23T07:37:10.967Z
started_at: 2026-09-16T21:10:44.845Z
closed_at: 2026-09-23T07:37:10.966Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-bgs7 (URL open: HTTPS mirror, internal GitHub resolver, ref/path split, serving), with no public reducer SDK."
resolution: null
duplicate_of: null
---
Integrate the immutable Git-tree source into repository URL opening. selection.py resolves slash-containing ref/path candidates locally and returns a typed missing-ref request; mb-jlon alone performs bounded network fetch. Pin the result to a full OID and serve a leased GitRevisionSubject through the content-source lifecycle without switching or materializing a checkout. Cover default, non-default, slash branches, tags, offline/unavailable refs, two concurrent subjects, object leases, reclamation, and cli-github-branch-open.
