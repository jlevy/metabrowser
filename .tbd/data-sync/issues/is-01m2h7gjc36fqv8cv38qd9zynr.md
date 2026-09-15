---
type: is
id: is-01m2h7gjc36fqv8cv38qd9zynr
title: "Repository library Phase 1B-c: open any selected branch in a detached materialization"
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T00:29:47.265Z
updated_at: 2026-09-15T01:19:46.416Z
---
Integrate mb-z335 into repository URL opening. selection.py resolves slash-containing ref/path candidates locally and returns a typed missing-ref request; mb-jlon jobs.py alone performs the bounded network fetch. Pin the result to a full OID and serve the leased detached root through the existing inventory lifecycle without moving gitroot or a local branch. Cover default/non-default/slash branches, offline and unavailable refs, concurrent leases, reclamation, and cli-github-branch-open.
