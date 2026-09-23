---
type: is
id: is-01m2p1pszq015wyj1b3admbt8r
title: "Repository source boundary review: publish content-source PR"
kind: task
status: closed
priority: 1
version: 13
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
updated_at: 2026-09-23T06:18:32.635Z
started_at: 2026-09-16T21:24:54.997Z
closed_at: 2026-09-23T06:18:32.634Z
close_reason: "Source-boundary acceptance, CLI golden coverage and independent review are complete (spec box ticked). #216 was reviewed in the stabilization pass; the remaining acceptance and two further independent reviews are in PR #226 (codex/v012-foundation-stabilization, head f68c3045f40ee28aa3eb37b010511cf8923ccc0d, all nine checks green: https://github.com/jlevy/metabrowser/actions/runs/35825617023). Published as #216 and #226 in stack 218; not merged."
resolution: null
duplicate_of: null
---
Independently review RepositorySubject, ContentSource, AttachedFilesystemSubject, source capabilities, one-active-subject lifecycle, filesystem-only plugin API gating, route/inventory generalization, exact-root containment, CLI parity, and goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green acquisition head. Record exact stack evidence and final green CI. Do not merge.

## Notes

2026-09-22 follow-up: no work is held on tbd. All eight current stack PRs are ready for review; #217/#216 draft flags were removed at the user’s request after live ancestry, mergeability and green-CI checks. This changes mechanical mergeability, not feature completion or landing authorization. #216 is ready for review at b3c001a9. Source-boundary acceptance and review obligations remain; consumers are substantially implemented and the spec now separates that from evidence still owed.

Earlier history:
Source-boundary review now targets draft #216 https://github.com/jlevy/metabrowser/pull/216 (folded #156). Not a separate PR.
Parent: #217. Head: cursor/v011-git-revision-pin-bd04.
Do not merge. Review the source-boundary contract inside #216, then the stack.

2026-09-22 state reconciliation: source boundary and leased Git pin are consolidated in draft #216 at b3c001a96eed64eb77961c2b7165b103af98b77c, over #217 at 4d25dc9a. Seven checks green. No separate source-boundary PR is required; this bead and mb-hoae review the same consolidated layer. Current content-reader changes and source-kind browser/golden evidence still need complete disposition; mb-3z4d tracks the nontrivial pin golden. The new acquisition-error finding mb-sumg also affects pin entrypoints. Preserve open status until acceptance is met.
