---
type: is
id: is-01m0ghvrnps0hh3m8d28xvfn2j
title: Provide unbounded logical Git history with bounded rendering
kind: epic
status: closed
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
labels:
  - release:v0.9.0
dependencies: []
child_order_hints:
  - is-01m0vsbcvvw9t96g5a73pkpb5d
  - is-01m0vscnvzcjatq9nd43zvqnwa
  - is-01m0vscy963c6aphv6ga8wmxww
  - is-01m0vsd8dnak6hw2b87x5awch6
  - is-01m0vsdfqzprgm8x1pmmgw701g
created_at: 2026-08-20T21:40:01.845Z
updated_at: 2026-08-27T07:24:36.406Z
closed_at: 2026-08-27T07:24:36.405Z
close_reason: "All five ordered children are complete: measurement, replayable server continuation, bounded virtual window, integrated continuous history, and exact release validation. PR #86 at c1aaf48 is green and ready for review."
resolution: null
duplicate_of: null
---
Replace the 500-row product cutoff with continuous, demand-driven Git history. Keep browser DOM, client state, and server work bounded through measured virtualization, page/cache policy, graph-layout checkpoints, and a continuation cursor that does not become progressively more expensive with history depth. Preserve selection, keyboard navigation, commit routes, ref scope, lane continuity, recovery states, and explicit end-of-history behavior. Begin from the exact v0.8.0 release and target v0.9.0; measurement in mb-t875 remains the first implementation gate.

## Notes

Specification merged in PR #80 (d59ab77). v0.8.0 retains the released, bounded 500-commit panel; the complete measured continuation and virtualization chain is deliberately scheduled for v0.9.0. Child order is measurement (mb-t875), parallel continuation and virtual-window mechanisms (mb-abu2 and mb-ghju), integration (mb-vieq), then exact release validation (mb-0ev5).
