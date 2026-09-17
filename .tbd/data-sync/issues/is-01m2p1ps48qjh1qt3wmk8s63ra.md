---
type: is
id: is-01m2p1ps48qjh1qt3wmk8s63ra
title: "Repository library Phase 1A review: publish format-foundation PR"
kind: task
status: closed
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01m2p1pshr699c6pf8xqeer16j
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:31.495Z
updated_at: 2026-09-17T21:29:33.888Z
started_at: 2026-09-16T21:24:54.515Z
closed_at: 2026-09-17T21:29:33.887Z
close_reason: "Independent review of the Phase 1A layer (9 findings: unbounded config error body, future-format home written before refusal, reads repairing permissions, routes disagreeing on a damaged entry, three surviving mutants, unbounded quarantine names, leaked trash lock) plus a re-audit that confirmed every fix, re-ran the mutation set with no regressions, and cleared the layer to publish. Final polish round fixed the refusal-text defect, the future-format mode residual, page/record bounds, and added a not_private publication value. Published PR #140 (https://github.com/jlevy/metabrowser/pull/140) as stack #131 layer 10, base claude/v011-hosted-review-phase0d@01584dba (PR #139), head claude/v011-cache-format-foundation@18ec887029647cfcb828fc64b2faeef886356b35. All seven checks green. Not merged; landing remains with mb-n2ro."
resolution: null
duplicate_of: null
---
Independently review the frozen cache measurement decisions (mb-ire2), owner-only application-home storage (mb-xa0p), the f01 application-home, source/store records, logical cache routes, lock order, atomic publication, migration refusal, security, distribution, CLI parity, and goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green Phase 0D head. Record exact stack evidence and final green CI. Do not merge.
