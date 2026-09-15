---
type: is
id: is-01m2h7gjc36fqv8cv38qd9zynr
title: "Repository library Phase 1B-c: open any selected branch in a detached materialization"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T00:29:47.265Z
updated_at: 2026-09-15T00:42:54.676Z
---
Integrate the reusable mb-z335 materialization primitive into repository URL opening. Resolve slash-containing ref/path candidates against local and remote-tracking refs, fetch only an explicitly selected missing ref within configured bounds, pin it to a full object ID, and serve the leased detached root through the existing inventory lifecycle. Never move or dirty gitroot, advance a local branch, or fall back to a different revision. Add default/non-default/slash branch, offline, unavailable, concurrent lease, reclamation, and cli-github-branch-open coverage.
