---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.11 hosted-resource stack: land and retarget completed phase PRs"
kind: task
status: open
priority: 1
version: 15
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
  - stack:pr132
  - stack:pr133
dependencies:
  - type: blocks
    target: is-01m10vgw6vhq82cd495kvhh9gf
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-16T03:27:25.766Z
---
After explicit approval and after every formal Phase 0 and GitHub v0.11 publication bead records a green PR, land the completed stack in dependency order: Phase 0A, 0B.1, 0B.2, 0B.3, 0C.1, 0C.2, GitHub 2A, 2B, 3A, 3B, hosted review 4A direct view, GitHub 3C index, hosted review 4B navigation, and 4C anchors. Retarget each next PR to its landed base, inspect the exact new-base...HEAD diff, resolve stacking-only conflicts without broadening scope, rerun make verify, obtain final green CI, and confirm main contains each merged layer. This is the sole landing owner; it never blocks constructing a later stack layer on the exact current green PR head, and it never merges without explicit user approval.

## Notes

PRs #125, #130, #132, and #133 are open draft stack layers. PR #132 is CLEAN with all seven checks green at e9dc37fcc7d19017fcb7094cc9aba5f760db2390, based on PR #130 head 0e8819c6ebc56739f1d3609064b8aaa86ea2d9ea. PR #133 is the completed Phase 0B.2 layer at 74dad3588d6de658ab2c56cf76711b39f0d3a496, based exactly on #132, with all seven checks green. Review records: https://github.com/jlevy/metabrowser/pull/132#issuecomment-5690698075 and https://github.com/jlevy/metabrowser/pull/133#issuecomment-5691564052. Continue stacking later phases without landing; landing still requires explicit approval and exact-diff revalidation for every PR.
