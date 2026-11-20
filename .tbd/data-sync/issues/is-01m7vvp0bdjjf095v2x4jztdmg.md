---
type: is
id: is-01m7vvp0bdjjf095v2x4jztdmg
title: "Files overview: less, uniform bar indent; legend names up to 9 file types at >= 1% plus Other"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T06:53:10.379Z
updated_at: 2026-11-20T06:53:10.379Z
---
Owner, 2026-11-20: 'on the Files overview section of the main files view, we don't need to indent the bars quite so much. the longest headings are words like "documentation" and "markdown" (under the toggle) and we want a uniform indent, so it shouldn't be too far to the left, but it could be a bit further left consistently. Also, let's include more file types in the legend, up to 9 (plus Other, so up to 10)' and 'but only if they are >= 1%'. Today LEGEND_TYPE_LIMIT = 5 and the share test is strictly > LEGEND_MINIMUM_SHARE_PERCENT (1) in src/metabrowser/file_type_legend.py.
