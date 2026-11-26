---
type: is
id: is-01m8bg139z95kertfgrezqqksx
title: "Layer 3: the core record without operational status"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/883
    at: 2026-11-26T12:06:42.216Z
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bg14grjg4kqt1bvhan6v5g
parent_id: is-01m8be447e9931hjyw4nrg4qxe
hold: null
hold_until: null
created_at: 2026-11-26T08:37:21.855Z
updated_at: 2026-11-26T22:22:46.584Z
started_at: 2026-11-26T10:18:37.877Z
closed_at: 2026-11-26T22:22:46.584Z
close_reason: "Merged to main with stack #877 (jlevy/metabrowser#876, #879, #883, #884), merge 68c54f030."
resolution: null
duplicate_of: null
---
Remove mergeable from PullRequest and cores and the checks parts from PullRecord; raise PULL_RECORD_SCHEMA; freshness reads the status; the Checks tab draws from the envelope's checks in GitHub's buckets; arch doc.
