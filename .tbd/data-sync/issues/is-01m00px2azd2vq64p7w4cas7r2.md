---
type: is
id: is-01m00px2azd2vq64p7w4cas7r2
title: Sort File Types rows by the active rollup measure
kind: feature
status: open
priority: 2
version: 2
labels:
  - browser
  - folder-overview
dependencies:
  - type: blocks
    target: is-01m00prch1akzeds6rnwc4rkwy
parent_id: is-01m00nzbe12ws4pm4870qgr3q1
created_at: 2026-08-14T18:00:16.478Z
updated_at: 2026-08-14T18:00:17.006Z
---
Sort every direct-child row collection in the overview File Types hierarchy by the currently selected rollup measure.

Required behavior:
- Within each subsection, order rows by descending value for the active metric: file count in Files mode and apparent bytes in Bytes mode.
- Use the active population as well: when Show ignored is unchecked, rank by unignored values; when checked, rank by all-file values.
- Keep structural subsection headings in registry order. Apply dynamic ranking only to rows within each section, including semantic families, family extension children, No extension basenames, Other types raw extensions, and expandable remainder children.
- Resolve ties deterministically by descending value of the other metric, then stable normalized key. Live refreshes with unchanged values must not reorder rows.
- Recompute the visible top ten and the aggregate N more remainder whenever metric or ignored scope changes. The aggregate row remains after the ten visible rows and exactly sums the newly hidden set.
- Reorder existing keyed DOM rows instead of remounting them so family disclosure state, subsection expansion state, focus, and event handlers are preserved where identities remain valid.
- Do not show partially reranked data. Metric and population transitions must use one complete snapshot and update the list and aggregate row atomically.
- Update File Rollup Format projection or expansion ordering parameters as needed so the client can obtain the true top ten without relying on a prefix ranked for another metric.
- Test skewed file-versus-byte examples, ignored-scope changes, ties, zero values, live updates, disclosure-state retention, and exact aggregate conservation.
