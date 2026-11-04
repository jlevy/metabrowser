---
type: is
id: is-01m0k536rmz4gptv9bzhftagk1
title: One rollup control row, or a written reason for two
kind: chore
status: closed
priority: 3
version: 5
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
hold: null
hold_until: null
created_at: 2026-08-21T21:54:37.460Z
updated_at: 2026-11-04T17:14:29.719Z
started_at: 2026-11-01T16:21:29.462Z
closed_at: 2026-11-04T17:14:29.719Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
The folder Overview and the Treemap both drive the same rollup state, and both build their own control row for it.

Overview now mounts one row carrying both halves — `rollupControls.mount(controls)` with no parts argument. The Treemap still mounts them separately, `mount(metricControls, {metric: true, ignored: false})` and `mount(scopeControls, {metric: false, ignored: true})`, because its layout puts them in different places.

That is defensible on its own, but it means the parts argument exists for exactly one caller, and the two surfaces present the same pair of controls with different adjacency. Worth deciding deliberately: either the Treemap adopts the single row and the parts argument goes away, or the split stays and the reason is written down beside it.

The wider pattern is the thing to look for. Two independent derivations of one quantity is what produced the measure bug fixed in #62: Overview computed its breakpoints against its own host while KPress computed the same boundary against the preview pane, and they crossed 75rem about 25px apart. Places worth a look: the treemap's own width tokens against the Overview column, the folder totals against the treemap's totals heading, and any other `@container` query that is not the shared `kpress-doc`.

## Notes

2026-11-01: fixed in PR #276, open, CI green at its last read. Close when it merges; its required review has not run.
