---
type: is
id: is-01m2p1pszq015wyj1b3admbt8r
title: "Repository source boundary review: publish content-source PR"
kind: task
status: in_progress
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - stack:publication
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m0dkj0gqvpzpxm7t1tpshf30
  - type: blocks
    target: is-01m2nzb0geg0hkaapyvj0hdb49
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:32.374Z
updated_at: 2026-09-23T00:23:22.825Z
started_at: 2026-09-16T21:24:54.997Z
---
Independently review RepositorySubject, ContentSource, AttachedFilesystemSubject, source capabilities, one-active-subject lifecycle, filesystem-only plugin API gating, route/inventory generalization, exact-root containment, CLI parity, and goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green acquisition head. Record exact stack evidence and final green CI. Do not merge.

## Notes

Source-boundary review now targets draft #216 https://github.com/jlevy/metabrowser/pull/216 (folded #156). Not a separate PR.
Parent: #217. Head: cursor/v011-git-revision-pin-bd04.
Do not merge. Review the source-boundary contract inside #216, then the stack.

2026-09-22 state reconciliation: source boundary and leased Git pin are consolidated in draft #216 at b3c001a96eed64eb77961c2b7165b103af98b77c, over #217 at 4d25dc9a. Seven checks green. No separate source-boundary PR is required; this bead and mb-hoae review the same consolidated layer. Current content-reader changes and source-kind browser/golden evidence still need complete disposition; mb-3z4d tracks the nontrivial pin golden. The new acquisition-error finding mb-sumg also affects pin entrypoints. Preserve open status until acceptance is met.
