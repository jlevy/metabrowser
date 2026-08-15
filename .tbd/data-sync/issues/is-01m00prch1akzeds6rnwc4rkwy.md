---
type: is
id: is-01m00prch1akzeds6rnwc4rkwy
title: Add ten-row aggregate disclosures to File Types subsections
kind: feature
status: closed
priority: 2
version: 2
labels:
  - browser
  - folder-overview
dependencies: []
parent_id: is-01m00nzbe12ws4pm4870qgr3q1
created_at: 2026-08-14T17:57:43.072Z
updated_at: 2026-08-14T19:02:48.012Z
closed_at: 2026-08-14T19:02:48.011Z
close_reason: Every repeated child list now presents at most ten rows plus an exact iconless N more disclosure, recursively and accessibly.
---
Apply one bounded disclosure grammar to every repeated child list in the overview File Types section.

Required behavior:
- Show at most the first ten direct child rows in each subsection while collapsed.
- When more children exist, append one aggregate disclosure row labeled with the hidden count, preferably N more to avoid colliding with the semantic Other types parent.
- Give the aggregate row the exact file and byte totals, percentages, and normalized bars for all hidden direct children. It is an aggregate heading and therefore has no file-type icon.
- Use the shared trailing-chevron disclosure treatment. The remainder is collapsed by default, expands to reveal every hidden child in deterministic order, and can be collapsed again without disturbing unrelated family disclosures.
- Apply the rule consistently to semantic group rows, expanded family extension children, No extension basenames, Other types raw extensions, and any future File Rollup Format subsection.
- Count only direct siblings at each level. Nested children do not consume the ten-row budget of their parent section.
- Keep expansion state stable across live updates when the subsection identity remains valid, and discard stale state on navigation or identity change.
- While expanded children are being acquired, use the shared rollup loading block and reveal the completed remainder atomically. Do not show partial rows or temporary zero aggregates.
- Preserve keyboard access, aria-expanded and aria-controls, row hierarchy, responsive column alignment, metric and ignored-file filtering, and correct empty or exactly-ten behavior.
- Add model, DOM, accessibility, live-update, and high-cardinality tests including 0, 10, 11, and 27 direct children.
