---
type: is
id: is-01m2kwk6h6pzxanejy6c339r08
title: "v0.11 GitHub Phase 2A base: converge format and repository prerequisites"
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - stack:base
dependencies:
  - type: blocks
    target: is-01m2h7jjga1ge5dzvs913n5fgs
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m2kw2b66x74xxjjtdp3wrsr4
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T01:16:42.405Z
updated_at: 2026-09-16T21:12:28.672Z
started_at: 2026-09-16T21:12:28.672Z
---
After the Phase 0C.2 publication and the repository-cache, cache-golden, untrusted-profile, and Git-status prerequisite evidence are green, create or select one named integration head containing every exact prerequisite commit. Record its branch name and immutable OID, verify each prerequisite OID is an ancestor, and run make verify on that convergence head. This bead never merges a PR; it supplies the one exact base for GitHub Phase 2A and prevents an either-or ancestry choice.
