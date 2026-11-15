---
type: is
id: is-01m7g6xwyrh1zfe6dh3tttsnsf
title: "Files Group by: rows read By age and By file type"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T18:18:50.200Z
updated_at: 2026-11-15T18:18:50.200Z
---
The user's request (2026-11-15), verbatim:

"the grouping menu in Files should have "By age" and "By file type" (add the "By")"

Today `filterGroupOptions` in static/app.js gives the rows the labels "Age" and "File type", with the summaries "By age" and "By file type" on the closed trigger.

Done when the Group by menu's rows read "By age" and "By file type", matching the trigger, with "No grouping" unchanged. A Git revision still offers no age. The Files Chrome test, any golden or session that records the labels, docs/design-system.md ("Grouping the Files Tree") and the CHANGELOG say so.
