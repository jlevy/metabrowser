---
type: is
id: is-01m00phrnxt0gptpykhzwy1s36
title: Unify folder rollup metric and ignored-file controls
kind: feature
status: open
priority: 2
version: 2
labels:
  - browser
  - folder-controls
dependencies:
  - type: blocks
    target: is-01m00phs4p1dvrzhgay8fqvwwr
parent_id: is-01m00nzbe12ws4pm4870qgr3q1
created_at: 2026-08-14T17:54:06.139Z
updated_at: 2026-08-14T17:54:06.613Z
---
Create one folder-rollup control and state abstraction shared by the overview File Types breakdown and the treemap.

Required behavior:
- Render the existing Bytes versus Files exclusive chooser and a Show ignored checkbox through one reusable folder-plugin component built on the public filter-controls design system.
- Default Show ignored to unchecked for new or missing preferences. Preserve a valid explicit saved preference and migrate the existing treemap preference shape without losing the metric choice.
- Use one canonical state contract and preference key so the two views present identical labels, keyboard and accessibility behavior, and synchronized choices when switching between overview and treemap.
- Excluding ignored files must make both consumers use unignored file and byte weights; including them must use complete weights without refetching when the loaded rollup snapshot already contains both.
- Keep the component consumer-agnostic within the folder plugin: it emits normalized state changes and does not own overview tables or treemap layout.
- Place the controls immediately below the File Types heading in overview and in the equivalent top control area of treemap.
- Test defaults, persisted-state migration, cross-view consistency, accessibility state, and both metric and ignored-file changes.
