---
type: is
id: is-01m7vvp0bdjjf095v2x4jztdmg
title: "Files overview: less, uniform bar indent; legend names up to 9 file types at >= 1% plus Other"
kind: task
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T06:53:10.379Z
updated_at: 2026-11-20T16:53:02.243Z
started_at: 2026-11-20T06:53:46.204Z
closed_at: 2026-11-20T07:59:52.725Z
close_reason: "Merged in PR 650: legend names up to 9 families at >= 1% plus Other; overview label column 130px measured."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: e27a0dd6-6f9c-4836-a87e-7ae786f6e0c2
    linked_at: 2026-11-20T16:53:02.234Z
---
Owner, 2026-11-20: 'on the Files overview section of the main files view, we don't need to indent the bars quite so much. the longest headings are words like "documentation" and "markdown" (under the toggle) and we want a uniform indent, so it shouldn't be too far to the left, but it could be a bit further left consistently. Also, let's include more file types in the legend, up to 9 (plus Other, so up to 10)' and 'but only if they are >= 1%'. Today LEGEND_TYPE_LIMIT = 5 and the share test is strictly > LEGEND_MINIMUM_SHARE_PERCENT (1) in src/metabrowser/file_type_legend.py.
