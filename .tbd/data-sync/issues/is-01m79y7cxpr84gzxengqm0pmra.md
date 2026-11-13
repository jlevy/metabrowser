---
type: is
id: is-01m79y7cxpr84gzxengqm0pmra
title: Switching to the Commits tab selects the most recent commit
kind: feature
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T07:51:17.685Z
updated_at: 2026-11-13T09:21:18.718Z
closed_at: 2026-11-13T09:21:18.717Z
close_reason: "Done in jlevy/metabrowser#395: every switch to Commits selects the newest commit; explicit commits win; recovery and startup paths fixed in review. Reviews A, B, C (approve). Merges once CI is green."
resolution: null
duplicate_of: null
---
The user, 2026-11-12: when the user switches to the Commits tab, the most recent commit should always be selected automatically. Stacked on #390's branch with the go-home change.

## Notes

2026-11-13: jlevy/metabrowser#395, 19a36c5b: every switch to Commits selects the newest commit; an explicit /commit/<rev> wins; no blank frame while history loads. Review A running.
