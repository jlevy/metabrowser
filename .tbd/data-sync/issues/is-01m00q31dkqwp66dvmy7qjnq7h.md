---
type: is
id: is-01m00q31dkqwp66dvmy7qjnq7h
title: Show shared Totals context above the treemap
kind: feature
status: closed
priority: 2
version: 2
labels:
  - browser
  - treemap
dependencies: []
parent_id: is-01m00nzbe12ws4pm4870qgr3q1
created_at: 2026-08-14T18:03:32.132Z
updated_at: 2026-08-14T19:02:48.248Z
closed_at: 2026-08-14T19:02:48.247Z
close_reason: Treemap now reuses the fixed Total/Ignored renderer above shared controls, keeps totals scope-independent, and removes routine footer copy while retaining exceptional status.
---
Add the same rollup totals presentation used by the overview above the treemap and remove the redundant steady-state footer.

Required behavior:
- Render a non-collapsible heading labeled Totals above the treemap, followed by exactly the Total and Ignored rows.
- Reuse the shared totals row model, renderer, bar treatment, formatters, emphasis rules, responsive columns, and design tokens from overview File Totals. Do not fork a treemap-only table implementation.
- Total reports the complete directory population and Ignored reports its ignored subset, independently of the Show ignored checkbox that controls treemap geometry.
- Place the general context first, followed by the shared Bytes versus Files and Show ignored controls, then the treemap viewport.
- Do not add a trailing chevron or disclosure state to the Totals heading in treemap; this compact context is always visible.
- Remove the bottom steady-state text such as 282 files · 3.5 MB · scan: done · ignored hidden. File and byte values now live in Totals, ignored visibility lives in the checkbox, and completed scan state needs no caption.
- Preserve dedicated accessible feedback for genuinely exceptional states such as loading, failed indexing, unavailable data, or a terminal truncated index. Do not retain the old footer merely to carry routine status.
- Update totals atomically with the treemap from one completed rollup snapshot, and prevent prior-path or prior-filter responses from updating either half.
- Add DOM and CSS behavior tests for content, ordering, non-collapsible semantics, shared renderer identity, ignored-scope independence, footer removal, exceptional states, responsive layout, and disposal.
