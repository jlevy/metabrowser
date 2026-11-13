---
type: is
id: is-01m7awmpdrtg05jbp6azj78jjh
title: Diff views carry no explanatory notes; the Rendered/Source toggle explains itself
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T16:42:50.679Z
updated_at: 2026-11-13T16:55:24.829Z
closed_at: 2026-11-13T16:55:24.828Z
close_reason: "Done in jlevy/metabrowser#397 (d06c7a17, 6cc4a410): both 'Source shows…' notes removed; behavior kept silent. Review A approved with two doc Lows, fixed. Merges once CI is green."
resolution: null
duplicate_of: null
---
The user, 2026-11-13: remove superfluous notes like 'Source shows additional changes.' from the diff viewer. The Rendered/Source toggle should be clear on its own. Follow-up to mb-lw70 (#394), which removed 'Rendered diff unavailable. Showing source.' but kept this one. Sweep the diff views (core diff, rendered Markdown diff, PR files) for every similar meta-note about rendering, sources, or views, and remove them; keep only real errors the reader must act on.

## Notes

2026-11-13: jlevy/metabrowser#397 (claude/ui-diff-no-notes to main), d06c7a17: removes 'Source shows changes not shown here.' and 'Source shows additional changes.' and their style; behavior kept silent. Limit to tell the user: Rendered omits changes with no visible counterpart (link targets, alt text, comments, whitespace), so such a block reads as unchanged. Review A running.
