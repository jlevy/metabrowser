---
type: is
id: is-01m8bg139z95kertfgrezqqksx
title: "Layer 3: the core record without operational status"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8bg14grjg4kqt1bvhan6v5g
parent_id: is-01m8be447e9931hjyw4nrg4qxe
created_at: 2026-11-26T08:37:21.855Z
updated_at: 2026-11-26T08:37:23.096Z
---
Remove mergeable from PullRequest and cores and the checks parts from PullRecord; raise PULL_RECORD_SCHEMA; freshness reads the status; the Checks tab draws from the envelope's checks in GitHub's buckets; arch doc.
