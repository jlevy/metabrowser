---
type: is
id: is-01kzrtbtsh9k6p8x84rta84y4p
title: Assess and publish Metabrowser v0.3.0 minor release
kind: task
status: in_progress
priority: 1
version: 19
labels: []
dependencies: []
child_order_hints:
  - is-01kzs1ky5mhg44p2n3tgv204sc
  - is-01kzs3c844hxhn5fmbxx8j5z1r
  - is-01kzs4vct70w4b81px21hj3dcn
  - is-01kzs5y3mbvz1151xyeg83znnj
  - is-01kzsbeh7nmvevgsmyr9w174d5
  - is-01kzsc71m2gs2sgsjheqemj7v2
  - is-01kzsd1epcab6ghygv2syte5he
  - is-01kzse0dcec8030qn0akzvar9w
  - is-01kzsgf1xeeqrkhzfssqa95qs6
created_at: 2026-08-11T16:26:50.545Z
updated_at: 2026-08-11T22:53:04.813Z
---
Review all user-visible changes since v0.2.0, triage outstanding defects for release blockers, validate the filtering/search stabilization release, prepare accurate v0.3.0 notes, run the complete release gate, publish the GitHub release, verify PyPI artifacts and public smoke tests, and confirm CI.

## Notes

Release audit remains ready for v0.3.0 after additional stability fixes. Filtering, Quick File, KPress 0.3.2, design, security documentation, Agent Skill, generic file-browser documentation, and the 90-second Live definition are covered. Filter settings are transient; durable appearance settings persist. UI messages, aggregate Docs/Code/Data tallies, and Ctrl-C shutdown behavior are corrected. Default logs now suppress routine timings and lifecycle noise. Bounded SSE queue gaps emit a resynchronization marker, end affected streams, and make browsers reconnect for fresh snapshots instead of remaining silently stale. Agent-log event filters use the shared wrapping filter-chip layout, joined segmented controls remain single-row, and the complete agent-log visual layer uses accessible semantic tokens in both themes. Quick File now separates placeholder guidance from status scope, progress, matches, empty results, and recovery; all counts are localized. The design system defines text roles, state language, brevity, punctuation, accessibility, and a mandatory Chrome-copy review for every changed interface surface. Symlinks are explicit non-expanded leaves with a Lucide leading icon, do not pollute file aggregates or filters, preserve served-root containment, and surface actionable link-target errors. Full make verify passes with 890 tests and 28 golden scenarios. PR #30 is mergeable and all refreshed required checks pass at 47eb67b; Cursor Bugbot completed as skipped. The separate watchfiles kernel-overflow limitation mb-pn95 remains deferred because the dependency does not surface notify rescan flags and requires broader reconciliation work. Release remains intentionally uncut while further fixes are reviewed.
