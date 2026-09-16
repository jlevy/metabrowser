---
type: is
id: is-01m2p1prnv5sdvx5atj08ckqn2
title: "Shared repository/provider mirror design review: publish formal stacked PR"
kind: task
status: in_progress
priority: 1
version: 7
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - design
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2nz8zzgxsw9yzsgekxy82sr
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:31.034Z
updated_at: 2026-09-16T22:31:53.408Z
started_at: 2026-09-16T21:24:54.275Z
---
Independently review the corrected repository-subject, shared worktree-free store, provider-mirror, capability, locking, lease, and phased-delivery architecture. Resolve every finding through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on exact green Phase 0C.2 PR #136 head. Record PR URL, base/head branches and immutable OIDs, formal stack view, review evidence, and final green CI. Do not merge; mb-n2ro alone owns explicit-approval landing and retargeting.

## Notes

Formal PR #138: https://github.com/jlevy/metabrowser/pull/138. Exact base codex/v011-hosted-review-phase0c2@b907bb2734929cd0858207ba5d73639aee168636; head codex/v011-shared-repository-mirror-design@dc91cd2d6dbfd670aa28b7d148fbb88ee79379b9. gh stack submit registered it as layer 8 after PRs #125, #130, #132, #133, #134, #135, and #136. Two architecture reviews and two bead-graph audits resolved to zero actionable findings. Final local make verify passed 2349 tests with 1 skipped, 124 goldens, and every lint/type/parity/audit/build/distribution gate. All seven GitHub checks are green: lint, distribution, Python 3.12, 3.13, 3.14, 3.14t, and stack integration. Awaiting the final independently posted PR review disposition; no merge performed.
