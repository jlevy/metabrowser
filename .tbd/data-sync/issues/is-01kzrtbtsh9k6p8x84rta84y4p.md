---
type: is
id: is-01kzrtbtsh9k6p8x84rta84y4p
title: Assess and publish Metabrowser v0.3.0 minor release
kind: task
status: in_progress
priority: 1
version: 11
labels: []
dependencies: []
child_order_hints:
  - is-01kzs1ky5mhg44p2n3tgv204sc
  - is-01kzs3c844hxhn5fmbxx8j5z1r
  - is-01kzs4vct70w4b81px21hj3dcn
  - is-01kzs5y3mbvz1151xyeg83znnj
  - is-01kzsbeh7nmvevgsmyr9w174d5
created_at: 2026-08-11T16:26:50.545Z
updated_at: 2026-08-11T21:38:07.679Z
---
Review all user-visible changes since v0.2.0, triage outstanding defects for release blockers, validate the filtering/search stabilization release, prepare accurate v0.3.0 notes, run the complete release gate, publish the GitHub release, verify PyPI artifacts and public smoke tests, and confirm CI.

## Notes

Release audit remains ready for v0.3.0 after additional stability fixes. Filtering, Quick File, KPress 0.3.2, design, security documentation, Agent Skill, generic file-browser documentation, and the 90-second Live definition are covered. Filter settings are transient; durable appearance settings persist. UI messages, aggregate Docs/Code/Data tallies, and Ctrl-C shutdown behavior are corrected. Default logs now suppress routine timings and lifecycle noise. Bounded SSE queue gaps emit a resynchronization marker, end affected streams, and make browsers reconnect for fresh snapshots instead of remaining silently stale. Agent-log event filters use the shared joined multi-select primitive: every dynamic kind has a visible ARIA-backed state, count, readable label, and disposed listener. The full agent-log visual layer now uses plugin-owned semantic tokens with accessible light and dark palettes for summaries, record controls, dynamic kinds, and errors. The design system documents one role-based control family, and structural tests enforce the shared text, icon, filter, menu, and tab primitives. Full make verify passes with 884 tests, 28 golden scenarios, lint and type checks, public hygiene, audits, distribution inspection, and wheel smoke tests. PR #30 is mergeable and all six checks pass. The separate watchfiles kernel-overflow limitation mb-pn95 remains deferred because the dependency does not surface notify rescan flags and requires broader reconciliation work. Release remains intentionally uncut while further fixes are reviewed.
