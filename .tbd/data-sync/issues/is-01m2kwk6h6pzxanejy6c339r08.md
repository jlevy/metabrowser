---
type: is
id: is-01m2kwk6h6pzxanejy6c339r08
title: "v0.11 GitHub Phase 2A base: converge format, repository-store, and source prerequisites"
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
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
updated_at: 2026-09-16T21:15:13.598Z
started_at: 2026-09-16T21:12:28.672Z
---
After Phase 0C.2, the reviewed Phase 0D source-binding correction, repository-store acquisition and goldens, immutable Git-tree source, and untrusted-profile evidence are green, create or select one named integration head containing every exact prerequisite commit. Record branch and immutable OID, verify each prerequisite OID as an ancestor, run make verify, and verify the formal stack. This bead never merges a PR; it supplies the one exact base for repository URL opening and prevents either-or ancestry choices. Git-status is not an integrity prerequisite for a worktree-free store.
