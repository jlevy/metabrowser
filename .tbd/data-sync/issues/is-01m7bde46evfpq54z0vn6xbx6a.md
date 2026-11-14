---
type: is
id: is-01m7bde46evfpq54z0vn6xbx6a
title: 'Pulls file tree: a late empty refresh leaves stale rows under "No changed files."'
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-13T21:36:21.197Z
updated_at: 2026-11-14T00:49:44.378Z
---
Found while fixing mb-ld8g (#406), present on main too. When a late refresh lists 0 files, a drawn Pulls file tree keeps its old rows under the line "No changed files." with no offer: `withheld` is true with 0 rows held, and `describeFileTree` words an offer only when `withheld > 0`.

Reproduction: `attic/emptied-late.mjs` in the ui-pulls-expand worktree gives {"rows":4,"line":"No changed files.","offer":null}.

Done when: a drawn tree whose list becomes empty either shows the empty state or offers to show it, never stale rows under a contradicting line; pinned in the opening session.
