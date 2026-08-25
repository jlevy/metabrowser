---
type: is
id: is-01m0ghvrnps0hh3m8d28xvfn2j
title: Provide unbounded logical Git history with bounded rendering
kind: epic
status: open
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
labels:
  - release:v0.8.0
dependencies: []
child_order_hints:
  - is-01m0vsbcvvw9t96g5a73pkpb5d
  - is-01m0vscnvzcjatq9nd43zvqnwa
  - is-01m0vscy963c6aphv6ga8wmxww
  - is-01m0vsd8dnak6hw2b87x5awch6
  - is-01m0vsdfqzprgm8x1pmmgw701g
created_at: 2026-08-20T21:40:01.845Z
updated_at: 2026-08-25T07:08:33.889Z
---
Replace the 500-row product cutoff with continuous, demand-driven Git history. Keep browser DOM, client state, and server work bounded through measured virtualization, page/cache policy, graph-layout checkpoints, and a continuation cursor that does not become progressively more expensive with history depth. Preserve selection, keyboard navigation, commit routes, ref scope, lane continuity, recovery states, and explicit end-of-history behavior. Target the next minor release; do not include this feature in v0.7.1.

## Notes

Specification merged in PR #80 (d59ab77) after CI passed on Python 3.12, 3.13, and 3.14 plus lint/audits and distribution validation. Implementation remains scheduled for v0.8.0; begin with mb-t875 measurement before either mechanism.
