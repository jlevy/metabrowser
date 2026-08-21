---
type: is
id: is-01m0k536rmz4gptv9bzhftagk1
title: One rollup control row, or a written reason for two
kind: chore
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-21T21:54:37.460Z
updated_at: 2026-08-21T21:54:37.460Z
---
The folder Overview and the Treemap both drive the same rollup state, and both build their own control row for it.

Overview now mounts one row carrying both halves — `rollupControls.mount(controls)` with no parts argument. The Treemap still mounts them separately, `mount(metricControls, {metric: true, ignored: false})` and `mount(scopeControls, {metric: false, ignored: true})`, because its layout puts them in different places.

That is defensible on its own, but it means the parts argument exists for exactly one caller, and the two surfaces present the same pair of controls with different adjacency. Worth deciding deliberately: either the Treemap adopts the single row and the parts argument goes away, or the split stays and the reason is written down beside it.

The wider pattern is the thing to look for. Two independent derivations of one quantity is what produced the measure bug fixed in #62: Overview computed its breakpoints against its own host while KPress computed the same boundary against the preview pane, and they crossed 75rem about 25px apart. Places worth a look: the treemap's own width tokens against the Overview column, the folder totals against the treemap's totals heading, and any other `@container` query that is not the shared `kpress-doc`.
