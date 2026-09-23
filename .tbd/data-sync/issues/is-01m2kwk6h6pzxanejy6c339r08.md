---
type: is
id: is-01m2kwk6h6pzxanejy6c339r08
title: "v0.12 GitHub Phase 2A base: verify the integrated format, source, store, and trust prerequisites"
kind: task
status: open
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - stack:base
  - release:v0.12.0
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
updated_at: 2026-09-23T00:23:26.090Z
started_at: 2026-09-16T21:12:28.672Z
---
After Phase 0C.2, the reviewed Phase 0D source-binding correction, repository-store acquisition and goldens, immutable Git-tree source, and untrusted-profile evidence are green, use the exact green untrusted-content profile layer head published by mb-d658, which the linear stack places directly after the immutable Git-tree source, as the one named integration head containing every exact prerequisite commit. Record branch and immutable OID, verify each prerequisite OID as an ancestor, run make verify, and verify the formal stack. This bead never merges a PR; it supplies the one exact base for repository URL opening and prevents either-or ancestry choices. Git-status is not an integrity prerequisite for a worktree-free store.

## Notes

2026-09-22 prerequisite reconciliation: HTML trust #209 is merged at fd65812b and main security hardening through #224 is an ancestor of current pushed #216 b3c001a9. No new standalone trust layer is needed. Record the final reviewed integration head only after source/pin and acquisition publication obligations close; verify its ancestry, forced untrusted behavior at new entrypoints, populated-cache isolation, and make verify. Future phase PRs extend the existing formal stack.
